from typing import Literal, Optional

from pydantic import Field

from lib.agents.literature_review import LiteratureReviewResponse
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class LiteratureReviewWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the literature review workflow."""

    type: Literal[WorkflowRunType.LITERATURE_REVIEW] = Field(
        WorkflowRunType.LITERATURE_REVIEW
    )


class LiteratureReviewState(BaseWorkflowState):
    """State for the literature review workflow."""

    type: Literal[WorkflowRunType.LITERATURE_REVIEW] = Field(
        WorkflowRunType.LITERATURE_REVIEW
    )
    config: LiteratureReviewWorkflowConfig
    file_id: str = Field(description="ID of the main document")
    literature_review: Optional[LiteratureReviewResponse] = Field(default=None)
