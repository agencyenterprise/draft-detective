from typing import List, Literal

from pydantic import Field

from lib.agents.claim_categorizer import ClaimCategorizationResponseWithClaimIndex
from lib.agents.claim_extractor import ClaimResponseWithChunkIndex
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimExtractionWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim extraction workflow"""

    type: Literal[WorkflowRunType.CLAIM_EXTRACTION] = Field(
        WorkflowRunType.CLAIM_EXTRACTION
    )


class ClaimExtractionState(BaseWorkflowState):
    """State for claim extraction workflow."""

    type: Literal[WorkflowRunType.CLAIM_EXTRACTION] = Field(
        WorkflowRunType.CLAIM_EXTRACTION
    )

    # Inputs
    file_id: str = Field(default="", description="File ID for backward compatibility")
    config: ClaimExtractionWorkflowConfig

    # Outputs
    claims: List[ClaimResponseWithChunkIndex] = Field(
        default_factory=list,
        description="List of extracted claims with chunk indices",
    )
    claim_categories: List[ClaimCategorizationResponseWithClaimIndex] = Field(
        default_factory=list,
        description="List of claim categorizations with claim indices",
    )
