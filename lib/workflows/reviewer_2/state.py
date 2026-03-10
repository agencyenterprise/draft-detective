from typing import Literal, Optional

from pydantic import Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class Reviewer2Config(BaseWorkflowConfig):
    """Configuration for the Reviewer 2 workflow."""

    type: Literal[WorkflowRunType.REVIEWER_2] = Field(WorkflowRunType.REVIEWER_2)


class Reviewer2State(BaseWorkflowState):
    """State for the Reviewer 2 workflow."""

    type: Literal[WorkflowRunType.REVIEWER_2] = Field(WorkflowRunType.REVIEWER_2)
    config: Reviewer2Config
    file_id: str = Field(default="", description="Main document file ID")
    peer_review_markdown: Optional[str] = Field(
        default=None,
        description="The peer review document as markdown (Sections 1-4)",
    )
    rebuttal_markdown: Optional[str] = Field(
        default=None,
        description="The rebuttal document as markdown",
    )
