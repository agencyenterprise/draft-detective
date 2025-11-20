from enum import IntEnum, StrEnum
from typing import List, Optional

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field

from lib.config.llm_models import gpt_5_model
from lib.models.agent import LangChainAgent


class EvidenceAlignmentLevel(StrEnum):
    UNVERIFIABLE = "unverifiable"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"


class ClaimEvidenceSource(BaseModel):
    quote: str = Field(
        description="A quote from the document that contains the evidence for the claim"
    )
    location: str = Field(
        description="The location of the quote in the document, e.g., 'page 3', 'section 2', 'figure 3', etc. Be as specific as possible"
    )
    reference_file_name: str = Field(
        description="The name of the reference file that contains the evidence for the claim, as provided in the 'list of references cited' section of the input"
    )


class RetrievedPassageInfo(BaseModel):
    """Information about a passage retrieved via RAG."""

    content: str = Field(description="The text content of the retrieved passage")
    source_file: str = Field(description="Name of the source file")
    cosine_distance: float = Field(
        description="Cosine distance (0-1, lower = more similar)"
    )
    chunk_index: int = Field(description="Index of the chunk within the source")


class ClaimSubstantiationResult(BaseModel):
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
        description="The sources that provide the evidence for the claim. If there are multiple sources, include all of them."
    )
    retrieved_passages: Optional[List[RetrievedPassageInfo]] = Field(
        default=None,
        description="Passages retrieved via RAG that were used for verification",
    )


class ClaimSubstantiationResultWithClaimIndex(ClaimSubstantiationResult):
    chunk_index: int
    claim_index: int


_claim_verifier_prompt = ChatPromptTemplate.from_template(
    """
# Task
You will be given a chunk of text from a document, a claim that is inferred from that chunk of text, and one or multiple supporting documents that are cited to support the claim.
Your task is to carefully read the supporting document(s) and determine wether the claim is supported by the supporting documents or not.
Return a rationale for why you think the claim is supported or not supported by the cited supporting document(s).

## Evidence alignment definitions

For each claim, output an evidence alignment level based on the following definitions:

- unverifiable: The supporting document(s) were not provided, or are inaccessible to confirm or deny the claim.
- supported: The claim is substantiated by the cited material. The reference clearly provides evidence or reasoning that matches both the claim’s factual scope and its evaluative tone.
- partially_supported: The citation provides related evidence but doesn’t fully substantiate the claim. It may support only part of the statement or use weaker phrasing than the claim implies. The mismatch usually involves scope, frequency, or tone rather than outright contradiction.
- unsupported: The cited material does not contain evidence for the claim. The connection may be irrelevant, tangential, outright fabricated, or the reference actually disagrees with the claim. This includes cases where the claim contradicts or reverses the source's position, or adds strong unsupported language that would mislead a reader about the author's intent. The claim may also use numbers or metrics that are not supported by the source or are not clearly derived from the source.

## Other instructions

- Citations may appear in the same chunk of the text that the claim belongs to, or potentially in a later chunk of the paragraph. So you will also be given info for the paragraph and all the citations in the paragraph. Use your judgement to determine whether a reference is cited close enough to the actual claim of the text for readers to understand the author's intent that the citation is supporting that claim or not. For example, if all citations of an introduction paragraph are at the end of the paragraph, then it's likely that the citations are supporting all the claims in the whole paragraph together, rather than just supporting the last sentence/chunk of the paragraph.

{domain_context}

{audience_context}

## The original document from which we are substantiating claims within a chunk
```
{full_document}
```

## The paragraph of the original document that contains the chunk of text that we want to substantiate
```
{paragraph}
```

## The chunk of text from the original document that contains the claim to be substantiated
```
{chunk}
```

## The claim that is inferred from the chunk of text to be substantiated
{claim}

{evidence_context_explanation}

## Supporting evidence cited in this chunk of text
{cited_references}

## Supporting evidence from elsewhere in the same paragraph
{cited_references_paragraph}

"""
)


class ClaimVerifierAgent(LangChainAgent):
    name = "Claim Verifier"
    description = "Substantiate a claim based on a supporting document"

    model = gpt_5_model
    temperature = 0.2
    output_schema = ClaimSubstantiationResult

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: RunnableConfig = None,
    ) -> ClaimSubstantiationResult:
        messages = _claim_verifier_prompt.format_messages(**prompt_kwargs)
        return await self.llm.ainvoke(messages, config=config)


claim_verifier_agent = ClaimVerifierAgent()
