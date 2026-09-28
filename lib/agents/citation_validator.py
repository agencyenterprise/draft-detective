"""Citation validator agent that reads document sections and validates citations."""

from enum import StrEnum
from typing import List, Optional

from langchain.agents import create_agent
from langchain.agents.structured_output import StructuredOutputError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.claim_verifier import ClaimEvidenceSource, EvidenceAlignmentLevel
from lib.agents.structured_output_salvage import ai_message_text, salvage_models
from lib.agents.tools.read_document import read_document
from lib.agents.tools.search_document import search_document
from lib.agents.tools.vector_search import vector_search
from lib.config.llm_models import gpt_5_6_terra_model
from lib.models.agent import LangChainAgent
from lib.skills import load_skill_prompt
from lib.workflows.context import ContextSchema


class TruthfulnessLabel(StrEnum):
    """LEGACY 6-category truthfulness taxonomy (RAND_RRA4269-1, Table 2).

    The agent no longer emits this — it now outputs the simpler four-value
    `EvidenceAlignmentLevel` (supported / partially_supported / unsupported /
    unverifiable). This enum is retained ONLY so workflow state persisted before
    the migration back to `EvidenceAlignmentLevel` still deserializes; the
    manifest maps it onto the new taxonomy for rendering."""

    TRUE_EXPLICIT = "true_explicit"
    TRUE_INFERRED = "true_inferred"
    PARTIALLY_TRUE = "partially_true"
    FALSE_CONTRADICTED = "false_contradicted"
    FALSE_NOT_IN_TEXT = "false_not_in_text"
    UNVERIFIABLE = "unverifiable"


class CitationAssessment(BaseModel):
    """The agent's output for a single assessed citation — exactly what the LLM
    must return, and nothing more (no persistence/legacy fields). The
    validate_section node converts this into the workflow's persisted
    `CitationIssueItem`, which keeps deprecated fields for retro-compatibility."""

    quoted_text: str = Field(
        description="The exact sentence or passage from the main document that contains the citation marker."
    )
    line_start: int = Field(
        description="1-indexed line number where quoted_text starts."
    )
    line_end: int = Field(description="1-indexed line number where quoted_text ends.")
    evidence_alignment: EvidenceAlignmentLevel = Field(
        description=(
            "How well the cited source supports the specific claim. Possible "
            f"values: {[e.value for e in EvidenceAlignmentLevel]}."
        ),
    )
    rationale: str = Field(
        description="Brief explanation of why the citation is or is not supported."
    )
    feedback: str = Field(
        description="Actionable suggestion for the author. Return 'No changes needed' if the citation is correct."
    )
    evidence_sources: List[ClaimEvidenceSource] = Field(
        description="All reference files that were checked when validating this citation.",
        default_factory=list,
    )
    citation_to_file_mapping: Optional[str] = Field(
        default=None,
        description=(
            "The full resolution chain from the in-text citation to the supporting "
            "file, with every intermediate jump you actually took, joined by ' → '. "
            "Always start with the citation marker as it appears in the text, and end "
            "with the supporting file name — or with 'No supporting file available' "
            "when no supporting file was matched. Include the bibliography entry as "
            "'Reference: \"<text>\"', and — when the citation is a footnote marker — "
            "the footnote entry it points to. Identify the bibliography entry by its "
            "text, never by a number or position in the bibliography; truncate a very "
            "long entry with ' [...]' but keep enough to identify it (authors, title, "
            "publisher, year). Examples — an author-year citation, with the long entry "
            "truncated: '(Appenzeller, Bornstein, and Casado, 2023) → Reference: "
            "\"Appenzeller, Guido, Matt Bornstein, and Martin Casado, “Navigating the "
            "High Cost of AI Compute,” Andreessen Horowitz, April 27, 2023 [...]\" → "
            "navigating_the_high_cost_of_ai_compute.md'; and a footnote marker, whose "
            "footnote entry is a jump of its own: '[^12] → Footnote 12: \"World Bank "
            "Group, “World Bank Open Data,” 2024\" → Reference: \"World Bank Group, "
            "“World Bank Open Data,” webpage, undated. As of October 15, 2024: "
            "https://data.worldbank.org/\" → world_bank_open_data.md'. "
            "Do not include file_id UUIDs in this string; the file_id belongs in each "
            "entry of evidence_sources."
        ),
    )


class SectionValidationResult(BaseModel):
    """The citation-validator agent's output for one document section."""

    issues: List[CitationAssessment] = Field(
        description="All citations identified in this section, with their validation results.",
        default_factory=list,
    )


class PartialSectionValidationError(Exception):
    """The model's response was cut off, but complete assessments were recovered.

    Carries the salvaged result so the caller can keep the assessments the model
    finished writing while still recording the section as incomplete. Always
    raised `from` the underlying structured-output error, so the provider
    metadata that explains the cut (`incomplete_details.reason`) stays reachable
    through the exception chain.
    """

    def __init__(
        self,
        result: SectionValidationResult,
        messages: List[BaseMessage],
        source: Exception,
    ) -> None:
        self.result = result
        self.messages = messages
        self.source = source
        super().__init__(
            f"Section validation output was truncated; recovered "
            f"{len(result.issues)} complete citation assessment(s) before the cut."
        )


# The citation-substantiation *method* lives in the portable `citation-support`
# skill (the single source of truth). This backend-only addendum carries the
# Draft-Detective specifics the skill omits: the assigned section, the concrete
# document-access tools, the bibliography→file mapping, and the structured-output
# field mapping. It is a `str.format` template — only this addendum is formatted,
# never the skill body (so the skill's literal braces are safe).
_ENV_GUIDANCE = """\


---

## Your assigned section

You are assigned a single section of the document; validate only citations whose
markers fall within it (this avoids duplicates from adjacent sections).

- **Main document file_id**: `{main_file_id}`
- **Section line range**: lines {start_line}–{end_line}
- **Section headings**: {section_headings}

## Tools in this environment

1. **read_document(file_id, start_line, end_line)**: Read a line range from any document (max 300 lines). Use the main document file_id to read your assigned section (or adjacent lines for boundary context), and a reference file_id to read source material.
2. **search_document(file_id, pattern)**: Search a document for lines matching a case-insensitive regex — use for specific terms, numbers, statistics, names, or exact phrases. To resolve a footnote marker, search the main document for the footnote entry (e.g. `^\\s*2\\.` or `\\[\\^2\\]`), read it, and match it to the bibliography-to-file mapping below.
3. **vector_search(file_id, query, top_k)**: Semantic search in a **supporting file** (not the main document) — use for conceptual or thematic claims where wording differs. Recommended top_k: 10.

Start by reading your assigned section with `read_document(main_file_id, {start_line}, {end_line})`, extending to adjacent lines if the boundaries fall mid-sentence or mid-block.

## Bibliography-to-file mapping

This table maps each bibliography entry to its supporting file. Use the file_id when calling the tools; a citation whose entry has no supporting file is `unverifiable`. Identify an entry by its text when reporting `citation_to_file_mapping` — the order of this table is not stable, so never refer to an entry by its position in it.

```
{reference_file_map}
```

## Output

Return `issues` — one `CitationAssessment` per citation you validate — each with:
- `quoted_text`: the exact sentence/passage containing the citation marker;
- `line_start` / `line_end`: its 1-indexed line range in the main document;
- `evidence_alignment`: one of `supported`, `partially_supported`, `unsupported`, `unverifiable`;
- `rationale`: a brief explanation of the judgment;
- `feedback`: an actionable suggestion for the author (`"No changes needed"` if the citation is correct);
- `evidence_sources`: every reference file you checked for this citation (with a quote, location, and file_id each);
- `citation_to_file_mapping`: every jump you took from the in-text marker to the supporting file, joined by ` → ` — see the field's own description for the exact shape.
"""


_USER_MESSAGE = "Please validate all citations in your assigned section."


class CitationValidatorAgent(LangChainAgent):
    name = "Citation Validator"
    description = "Validate citations in a document section against reference files"
    model = gpt_5_6_terra_model
    reasoning = {"effort": "medium", "summary": "auto"}

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[SectionValidationResult, List[BaseMessage]]:
        agent = create_agent(
            self.llm,
            [vector_search, search_document, read_document],
            context_schema=ContextSchema,
            response_format=SectionValidationResult,
        )

        try:
            result = await agent.ainvoke(
                {
                    "messages": [
                        SystemMessage(
                            content=load_skill_prompt("citation-support")
                            + _ENV_GUIDANCE.format(**prompt_kwargs)
                        ),
                        HumanMessage(content=_USER_MESSAGE),
                    ]
                },
                config={"recursion_limit": 80, **(config or {})},
                context=self.context,
            )
        except StructuredOutputError as e:
            partial = self._salvage(e)
            if partial is None:
                raise
            raise partial from e

        structured: SectionValidationResult = result["structured_response"]
        return structured, result["messages"]

    @staticmethod
    def _salvage(error: StructuredOutputError) -> Optional[PartialSectionValidationError]:
        """Recover the assessments a truncated response had already completed.

        LangChain raises before the agent returns, so the only record of the
        model's work is the `AIMessage` carried on the exception. Returns None
        when there is nothing to recover, leaving the caller to re-raise.
        """
        ai_message = getattr(error, "ai_message", None)
        if not isinstance(ai_message, AIMessage):
            return None

        salvaged = salvage_models(
            ai_message_text(ai_message), "issues", CitationAssessment
        )
        if not salvaged:
            return None

        return PartialSectionValidationError(
            SectionValidationResult(issues=salvaged), [ai_message], error
        )
