from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.claim_verifier import ClaimSubstantiationResultWithClaimIndex
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimReferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim reference validation workflow"""

    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    )
    domain: Optional[str] = Field(
        default=None, description="Domain context for more accurate analysis"
    )
    target_audience: Optional[str] = Field(
        default=None, description="Target audience context for analysis"
    )
    publication_date: Optional[str] = Field(
        default=None, description="Publication date of the document (YYYY-MM-DD format)"
    )


class ClaimReferenceValidationState(BaseWorkflowState):
    """State for the claim reference validation workflow."""

    # Inputs
    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    )
    config: ClaimReferenceValidationWorkflowConfig

    # Outputs
    substantiations: List[ClaimSubstantiationResultWithClaimIndex] = Field(
        default_factory=list,
        description="Claim substantiation results indexed by chunk_index and claim_index",
    )
