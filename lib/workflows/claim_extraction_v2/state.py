from typing import List, Literal

from pydantic import Field

from lib.agents.claim_categorizer import ClaimCategorizationResponseWithClaimIndex
from lib.agents.claim_extractor import ClaimResponseWithChunkIndex
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType

DEFAULT_PARAGRAPH_GROUP_WORD_LIMIT = 1000


class ClaimExtractionV2WorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim extraction v2 workflow."""

    type: Literal[WorkflowRunType.CLAIM_EXTRACTION_V2] = Field(
        WorkflowRunType.CLAIM_EXTRACTION_V2
    )

    paragraph_group_word_limit: int = Field(
        default=DEFAULT_PARAGRAPH_GROUP_WORD_LIMIT,
        description=(
            "Maximum word count per paragraph group batch. "
            "Consecutive paragraphs are grouped until this limit is reached."
        ),
    )


class ClaimExtractionV2State(BaseWorkflowState):
    """State for claim extraction v2 workflow."""

    type: Literal[WorkflowRunType.CLAIM_EXTRACTION_V2] = Field(
        WorkflowRunType.CLAIM_EXTRACTION_V2
    )

    # Inputs
    file_id: str = Field(default="", description="File ID for backward compatibility")
    config: ClaimExtractionV2WorkflowConfig

    # Outputs
    claims: List[ClaimResponseWithChunkIndex] = Field(
        default_factory=list,
        description="List of extracted claims with chunk indices",
    )
    claim_categories: List[ClaimCategorizationResponseWithClaimIndex] = Field(
        default_factory=list,
        description=(
            "List of claim categorizations with claim indices. "
            "Always empty for v2 (no categorization node)."
        ),
    )
