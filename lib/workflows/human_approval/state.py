"""State for human approval workflow."""

from enum import StrEnum
from typing import Optional

from pydantic import Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ApprovalCheckpoint(StrEnum):
    """Types of approval checkpoints."""

    REFERENCE_REVIEW = "reference_review"


class HumanApprovalConfig(BaseWorkflowConfig):
    """Config for human approval workflow."""

    type: WorkflowRunType = WorkflowRunType.HUMAN_APPROVAL
    checkpoint: ApprovalCheckpoint = Field(
        default=ApprovalCheckpoint.REFERENCE_REVIEW,
        description="The type of approval checkpoint",
    )

    @classmethod
    def requires_api_key(cls) -> bool:
        return False


class HumanApprovalState(BaseWorkflowState):
    """State for human approval workflow."""

    type: WorkflowRunType = WorkflowRunType.HUMAN_APPROVAL
    config: HumanApprovalConfig = Field(default_factory=HumanApprovalConfig)
    approved: bool = Field(default=False, description="Whether human has approved")
    approved_at: Optional[str] = Field(
        default=None, description="ISO timestamp when approved"
    )

