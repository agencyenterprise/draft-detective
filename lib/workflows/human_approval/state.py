"""State for human approval workflow."""

from typing import Optional

from pydantic import Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class HumanApprovalConfig(BaseWorkflowConfig):
    """Config for human approval workflow."""

    type: WorkflowRunType = WorkflowRunType.HUMAN_APPROVAL

    @classmethod
    def requires_api_key(cls) -> bool:
        return False


class HumanApprovalState(BaseWorkflowState):
    """State for human approval workflow."""

    type: WorkflowRunType = WorkflowRunType.HUMAN_APPROVAL
    config: HumanApprovalConfig
    approved: bool = Field(default=False, description="Whether human has approved")
    approved_at: Optional[str] = Field(
        default=None, description="ISO timestamp when approved"
    )

