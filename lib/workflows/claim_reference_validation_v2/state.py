from typing import List, Literal, Optional

from langchain_core.messages import AnyMessage
from pydantic import BaseModel, Field

from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimReferenceValidationV2ItemSource(BaseModel):
    quote: str = Field(
        description="A direct quote from the document that contains the evidence for the claim"
    )
    location: str = Field(
        description="The location of the quote in the document, e.g., 'page 3', 'section 2', 'figure 3', etc. Be as specific as possible"
    )
    supporting_document: str = Field(
        description="The full path to the supporting document that contains the evidence for the claim"
    )


class ClaimReferenceValidationV2Item(BaseModel):
    key_sentence: str = Field(
        description="The key sentence from the main document that is being validated. Should be a direct quote from the text."
    )
    line_start: int = Field(
        description="The start line of the key sentence in the main document"
    )
    line_end: int = Field(
        description="The end line of the key sentence in the main document"
    )
    evidence_alignment: EvidenceAlignmentLevel = Field(
        description=f"The degree of evidence that the supporting document(s) provides to support the claim. Possible values: {[e.value for e in EvidenceAlignmentLevel]}"
    )
    rationale: str = Field(
        description="A brief rationale for why you think the claim is substantiated or not substantiated by the cited supporting document(s)"
    )
    long_rationale: str = Field(
        description="A detailed rationale for why you think the claim is substantiated or not substantiated by the cited supporting document(s), in markdown format"
    )
    feedback: str = Field(
        description="A brief suggestion on how the issue can be resolved, e.g., by adding more supporting documents or by rephrasing the original chunk, etc. Return 'No changes needed' if there are no significant issues with the substantiation of the claim."
    )
    evidence_sources: List[ClaimReferenceValidationV2ItemSource] = Field(
        description="The sources that provide the evidence for the claim. If there are multiple sources, include all of them."
    )


class ClaimReferenceValidationV2Response(BaseModel):
    results: List[ClaimReferenceValidationV2Item] = Field(
        description="The results of the claim reference validation"
    )
    reasoning: str = Field(
        description="The step-by-step reasoning you used to perform the validation, in markdown format"
    )


class ClaimReferenceValidationV2Config(BaseWorkflowConfig):
    """Configuration for claim reference validation v2 workflow"""

    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    )


class ClaimReferenceValidationV2State(BaseWorkflowState):
    """State for claim reference validation v2 workflow."""

    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    )
    config: ClaimReferenceValidationV2Config
    messages: List[AnyMessage] = Field(
        default_factory=list, description="Messages from the LLM"
    )
    response: Optional[ClaimReferenceValidationV2Response] = Field(
        default=None,
        description="The response from the claim reference validation agent",
    )
