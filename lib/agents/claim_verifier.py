from enum import StrEnum
from typing import List, Optional

from langchain.agents import create_agent
from langchain_core.prompts import PromptTemplate
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.tools.read_document import read_document
from lib.agents.tools.search_document import search_document
from lib.agents.tools.vector_search import vector_search
from lib.config.llm_models import gpt_5_4_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema


class EvidenceAlignmentLevel(StrEnum):
    UNVERIFIABLE = "unverifiable"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"


class ClaimEvidenceSource(BaseModel):
    quote: str = Field(
        description="A quote from the document that contains the evidence for the claim. If no quote was found, return an empty string."
    )
    location: str = Field(
        description="The location of the quote in the document, e.g., 'page 3', 'section 2', 'figure 3', etc. Be as specific as possible. Don't use line numbers, but rather section titles or other section identifiers. If no location was found, return an empty string."
    )
    file_id: str = Field(
        description="The ID of the reference file that was checked as provided in the citation-to-file mapping."
    )


class ClaimVerificationItem(BaseModel):
    """Verification result for a single claim within a paragraph."""

    key_sentence: str = Field(
        description="The key sentence that contains the claim to be substantiated. Should be a direct quote from the text."
    )
    claim_number: int = Field(
        description="The number of the claim from the provided numbered list"
    )
    evidence_alignment: EvidenceAlignmentLevel = Field(
        description=f"The degree of evidence that the supporting document(s) provides to support the claim. Possible values: {[e.value for e in EvidenceAlignmentLevel]}"
    )
    rationale: str = Field(
        description="A brief rationale for why you think the claim is substantiated or not substantiated by the cited supporting document(s)"
    )
    feedback: str = Field(
        description="A brief suggestion on how the issue can be resolved, e.g., by adding more supporting documents or by rephrasing the original chunk, etc. Return 'No changes needed' if there are no significant issues with the substantiation of the claim."
    )
    evidence_sources: List[ClaimEvidenceSource] = Field(
        description="The sources/documents that were checked in the validation process. If there are multiple sources, include all of them. If no sources were checked, return an empty list."
    )
    citation_to_file_mapping: Optional[str] = Field(
        default=None,
        description="A string representation of the citation-to-file mapping that was used to check the evidence. Do not include file IDs. Null if no citation-to-file mapping was provided.",
    )


class ClaimSubstantiationResultWithClaimIndex(ClaimVerificationItem):
    chunk_index: int
    claim_index: int


class ParagraphVerificationResult(BaseModel):
    """Verification results for all claims in a paragraph."""

    claim_results: List[ClaimVerificationItem] = Field(
        description="A list of verification results, one for each claim in the numbered list"
    )


_system_prompt = PromptTemplate.from_template(
    """# Task

You are a claim verification specialist. You will be given a paragraph from a document and a numbered list of claims extracted from that paragraph. Your task is to verify each claim against the cited supporting documents using the available tools.

## Available Tools

1. **vector_search(file_id, query, top_k)**: Search a supporting document for passages relevant to a query using semantic vector search. You must provide the `file_id` from the citation-to-file mapping below, a natural language query describing the evidence you are looking for, and the `top_k` parameter to control how many passages to retrieve (recommended: 10). Best suited for conceptual or thematic claims where you need to find passages discussing a topic, argument, or idea.

2. **search_document(file_id, pattern)**: Search a supporting document for lines matching a regex pattern (case-insensitive). Returns matching lines with surrounding context and line numbers, similar to grep. Best suited for claims involving specific terms, numbers, statistics, names, exact phrases, or other precise textual content (e.g., searching for "42%" or a proper noun).

3. **read_document(file_id, start_line, end_line)**: Read a specific line range from a supporting document (1-indexed, max 300 lines per request). Use this tool to read surrounding context around a match found by `search_document`, or to read a specific section of a document when you already know the approximate location.

## Workflow

1. Read the paragraph and the list of claims carefully.
2. Review the citation-to-file mapping to understand which supporting files are available and which citations reference them.
3. For each claim, choose the most appropriate search strategy based on the nature of the claim:
   - Use `vector_search` when the claim is conceptual, thematic, or paraphrased, and you need to find passages that discuss the same idea even if the exact wording differs.
   - Use `search_document` when the claim contains specific data points, statistics, proper nouns, technical terms, or exact phrases that can be matched directly in the text.
   - Use both tools in combination when a claim involves both a specific fact and broader context—for example, use `search_document` to locate an exact figure, then `read_document` to understand the surrounding context, or use `vector_search` to find a relevant section and then `search_document` to confirm a specific detail within it.
4. After gathering evidence, evaluate each claim and produce a verification result.

## Evidence Alignment Definitions

For each claim, output an evidence alignment level based on the following definitions:

- **unverifiable**: The supporting document(s) were not provided, or are inaccessible to confirm or deny the claim.
- **supported**: The claim is substantiated by the cited material. The reference clearly provides evidence or reasoning that matches both the claim's factual scope and its evaluative tone.
- **partially_supported**: The citation provides related evidence but doesn't fully substantiate the claim. It may support only part of the statement or use weaker phrasing than the claim implies. The mismatch usually involves scope, frequency, or tone rather than outright contradiction.
- **unsupported**: The cited material does not contain evidence for the claim. The connection may be irrelevant, tangential, outright fabricated, or the reference actually disagrees with the claim. This includes cases where the claim contradicts or reverses the source's position, or adds strong unsupported language that would mislead a reader about the author's intent. The claim may also use numbers or metrics that are not supported by the source or are not clearly derived from the source.

## Other Instructions

- Citations may appear in the same chunk of text that a claim belongs to, or potentially in a later chunk of the paragraph. Use your judgement to determine whether a reference is cited close enough to the actual claim for readers to understand that the citation is supporting that claim. For example, if all citations of an introduction paragraph are at the end of the paragraph, then it's likely that the citations are supporting all the claims in the whole paragraph together.
- You MUST produce a result for every claim in the numbered list.
- When searching, try a couple of different query formulations if the first search doesn't return useful results, but don't over-search. Two or three searches per claim should usually be enough to find the relevant evidence. If you still can't find supporting evidence after a few targeted attempts, conclude with the best information you have rather than continuing to search exhaustively.

{domain_context}

{audience_context}
"""
)


class ClaimVerifierAgent(LangChainAgent):
    name = "Claim Verifier"
    description = "Verify claims in a paragraph by searching supporting documents"
    model = gpt_5_4_model
    temperature = 0.2

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> ParagraphVerificationResult:
        system_prompt = _system_prompt.invoke(prompt_kwargs)

        agent = create_agent(
            self.llm,
            [vector_search, search_document, read_document],
            system_prompt=system_prompt.to_string(),
            context_schema=ContextSchema,
            response_format=ParagraphVerificationResult,
        )

        user_message = _build_user_message(prompt_kwargs)

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"recursion_limit": 80, **(config or {})},
            context=self.context,
        )

        return result["structured_response"]


def _build_user_message(prompt_kwargs: dict) -> str:
    """Build the user message with paragraph, claims, and citation-to-file mapping."""
    parts = []

    parts.append(
        "## Paragraph from the original document\n"
        "```\n"
        f"{prompt_kwargs['paragraph']}\n"
        "```"
    )

    parts.append("## Claims to verify\n" f"{prompt_kwargs['claims_list']}")

    parts.append(
        "## Citation-to-file mapping\n"
        "Use the file_id values below when calling the search tools.\n\n"
        f"{prompt_kwargs['citation_file_mapping']}"
    )

    return "\n\n".join(parts)
