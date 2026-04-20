from enum import Enum
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field

from lib.agents.claim_verifier import ClaimSubstantiationResultWithClaimIndex
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimReferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim reference validation workflow"""

    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    )


class ParagraphVerificationStatus(str, Enum):
    """Status of a paragraph verification operation."""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class ParagraphVerificationItem(BaseModel):
    """Item for tracking individual paragraph verification with status."""

    paragraph_index: int = Field(description="The paragraph index being verified.")
    status: ParagraphVerificationStatus = Field(
        default=ParagraphVerificationStatus.PENDING,
        description="Current status of this paragraph verification.",
    )
    num_claims: int = Field(
        default=0,
        description="Number of claims being verified in this paragraph.",
    )
    substantiations: List[ClaimSubstantiationResultWithClaimIndex] = Field(
        default_factory=list,
        description="Verification results for claims in this paragraph.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message, present on failure.",
    )


def merge_paragraph_verifications(
    existing: List[ParagraphVerificationItem],
    new: List[ParagraphVerificationItem],
) -> List[ParagraphVerificationItem]:
    """Reducer to merge results by paragraph_index, preserving order.

    This reducer function is used by LangGraph to handle incremental updates
    from parallel verification operations. Each update overwrites the entry with
    the same paragraph_index, allowing status transitions from PENDING to
    COMPLETED/ERROR.
    """
    results_by_index = {r.paragraph_index: r for r in existing}

    for item in new:
        results_by_index[item.paragraph_index] = item

    return list(results_by_index.values())


class ClaimReferenceValidationState(BaseWorkflowState):
    """State for the claim reference validation workflow."""

    # Inputs
    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    )
    config: ClaimReferenceValidationWorkflowConfig

    # Incremental tracking (reducer-backed for fan-out)
    paragraph_verifications: Annotated[
        List[ParagraphVerificationItem], merge_paragraph_verifications
    ] = Field(default_factory=list)

    # Outputs (populated by finalize node)
    substantiations: List[ClaimSubstantiationResultWithClaimIndex] = Field(
        default_factory=list,
        description="Claim substantiation results indexed by chunk_index and claim_index",
    )
