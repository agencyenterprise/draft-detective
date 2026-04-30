"""Citation validator agent that reads document sections and validates citations."""

from typing import List, Optional

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.claim_verifier import ClaimEvidenceSource, EvidenceAlignmentLevel
from lib.agents.tools.read_document import read_document
from lib.agents.tools.search_document import search_document
from lib.agents.tools.vector_search import vector_search
from lib.config.llm_models import gpt_5_5_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class CitationIssueItem(BaseModel):
    """A citation that was identified as problematic or noteworthy."""

    quoted_text: str = Field(
        description="The exact sentence or passage from the main document that contains the citation marker."
    )
    line_start: int = Field(
        description="1-indexed line number where quoted_text starts."
    )
    line_end: int = Field(description="1-indexed line number where quoted_text ends.")
    evidence_alignment: EvidenceAlignmentLevel = Field(
        description="How well the cited source supports the claim being made."
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
            "Display-friendly summary of which bibliography entry was matched to "
            "which supporting file when checking this citation, e.g. "
            "'Smith (2020) → smith_2020.pdf'. Do not include file_id UUIDs in this "
            "string; the file_id belongs in each entry of evidence_sources."
        ),
    )


class SectionValidationResult(BaseModel):
    """Validation results for a single document section."""

    issues: List[CitationIssueItem] = Field(
        description="All citations identified in this section, with their validation results.",
        default_factory=list,
    )


_SYSTEM_PROMPT_TEMPLATE = """\
# Task

You are a citation validation specialist. You are assigned a section of an academic document. Your task is to find every statement in that section that cites a reference, then verify whether the cited source actually supports the claim being made.

## Your assigned section

- **Main document file_id**: `{main_file_id}`
- **Section line range**: lines {start_line}–{end_line}
- **Section headings**: {section_headings}

## Available Tools

1. **read_document(file_id, start_line, end_line)**: Read a line range from any document (max 300 lines). Use the main document file_id to read your section or surrounding context. Use a reference file_id to read the source material.

2. **search_document(file_id, pattern)**: Search a document for lines matching a regex pattern (case-insensitive). Use this for specific terms, numbers, statistics, names, or exact phrases.

3. **vector_search(file_id, query, top_k)**: Semantic search in a **supporting file** (not the main document). Use this to find passages discussing the same concept even if the exact wording differs. Recommended top_k: 10.

## Bibliography-to-file mapping

The following table maps each bibliography entry number to its supporting file. Use the file_id when calling the tools.

```
{reference_file_map}
```

## Citation Formats

Documents use citations in two main formats:

1. **Author-year**: e.g., `(Smith, 2020)`, `Smith (2020)`, `(Smith et al., 2020)`. These map directly to a bibliography entry — match them to the bibliography-to-file mapping by author and year.

2. **Footnote markers**: e.g., `[2]`, `[^2]`, superscript `²`. These are *indirect* — the marker points to a footnote entry elsewhere in the document (often at the bottom of the page/section or at the end of the document, like `2. Smith, 2020, Title of the work`). The footnote entry then points to the actual bibliography entry.
   - **Important**: Not every footnote is a citation. Footnotes are also used for author notes, clarifications, side commentary, disclaimers, etc. Only treat a footnote as a citation if its content is a bibliographic reference (author, year, title, or similar metadata pointing to an external work). If the footnote is commentary or a note, skip it — do not report it.
   - To resolve a footnote citation: use `search_document(main_file_id, ...)` to find the footnote entry (e.g., search for `^\\s*2\\.` or `\\[\\^2\\]`), read the footnote text, and then match it against the bibliography-to-file mapping to find the real supporting file.
   - **Validate the in-text marker, not the footnote entry.** A footnote entry line (e.g., `[^1]: Smith, 2020. Title of the work` or `1. Smith, 2020. Title of the work`) is the *target* of a marker, not a standalone in-text claim. Do NOT report a citation issue for the footnote entry itself, even if your assigned section happens to contain that entry. Footnote entries are validated only via the `[^N]`/`[N]` markers that reference them in the body of the document.

## Bibliography sections

Lines inside a `## References`, `## Bibliography`, or similar dedicated bibliography section are reference *entries*, not in-text citations. Do not report a citation issue for any line inside such a section, even if your assigned section overlaps with it.

## Workflow

1. Read your assigned section using `read_document(main_file_id, {start_line}, {end_line})`.
   - The section boundaries are approximate. Some documents are converted from PDFs and may have messy formatting. If the first or last lines appear to start or end mid-sentence, mid-paragraph, or mid-block element (e.g., table, equation), extend the read by calling `read_document(main_file_id, ...)` on adjacent lines before/after until you capture complete sentences and block elements. This ensures citations near section boundaries are evaluated with full context.
2. Identify every sentence or passage that includes a citation marker (author-year or footnote). Only consider markers whose position falls within lines {start_line}–{end_line} (avoids duplicates from adjacent sections).
3. For each cited statement:
   a. Resolve the citation to a bibliography entry:
      - **Author-year**: match directly to the bibliography-to-file mapping by author/year.
      - **Footnote**: locate the footnote entry in the main document with `search_document`, confirm it is a bibliographic reference (not commentary — if it's commentary, skip this marker entirely), then match the footnote's reference text to the bibliography-to-file mapping.
   b. Look up the corresponding file_id from the bibliography-to-file mapping.
   c. Search the reference file for evidence that supports the specific claim:
      - Use `vector_search` for conceptual or thematic claims.
      - Use `search_document` for specific data points, numbers, or terms.
      - Use `read_document` on the reference file to read surrounding context.
   d. Evaluate whether the source actually supports the claim.
4. If you need broader context around the cited text, use `read_document(main_file_id, ...)` to read adjacent lines.

## Evidence Alignment Definitions

- **unverifiable**: The supporting file was not provided or could not be searched.
- **supported**: The source clearly provides evidence that matches the claim's factual scope and tone.
- **partially_supported**: The source provides related evidence but doesn't fully substantiate the claim (scope, frequency, or tone mismatch).
- **unsupported**: The source does not contain evidence for the claim, contradicts it, or the citation is tangential or fabricated.

## Search Efficiency

- Two or three searches per citation are usually enough. If you cannot find supporting evidence after a few targeted attempts, conclude with the best information you have.
- Do not search exhaustively. Bias toward concluding rather than searching more.

{domain_context}

{audience_context}
"""


_USER_MESSAGE = "Please validate all citations in your assigned section."


class CitationValidatorAgent(LangChainAgent):
    name = "Citation Validator"
    description = "Validate citations in a document section against reference files"
    model = gpt_5_5_model
    temperature = 0.0
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

        result = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(
                        content=_SYSTEM_PROMPT_TEMPLATE.format(**prompt_kwargs)
                    ),
                    HumanMessage(content=_USER_MESSAGE),
                ]
            },
            config={"recursion_limit": 80, **(config or {})},
            context=self.context,
        )

        return result["structured_response"], result["messages"]
