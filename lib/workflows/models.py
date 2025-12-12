from enum import Enum
from operator import add
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field


class WorkflowError(BaseModel):
    """Error object for the overall workflow or specific chunks."""

    chunk_index: Optional[int] = Field(
        default=None,
        description="The index of the chunk that caused the error. This is None if the error occurred before the chunk was processed or in the overall workflow (not chunk-related).",
    )
    task_name: str = Field(description="The name of the task that caused the error.")
    error: str = Field(description="The error message.")


class BaseWorkflowState(BaseModel):
    """Base model for all workflow states."""

    errors: Annotated[List[WorkflowError], add] = Field(
        default_factory=list,
        description="Errors that occurred during the workflow execution.",
    )


class BaseWorkflowConfig(BaseModel):
    """Base model for all workflow configs."""

    project_id: Optional[str] = Field(
        default=None,
        description="The ID of the project that this workflow run should be associated with",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="The OpenAI API key to use for this workflow execution",
    )


class WorkflowRunType(str, Enum):
    CLAIM_SUBSTANTIATION = "claim_substantiation"
    METHODOLOGICAL_ALIGNMENT = "methodological_alignment"
    REFERENCE_DOWNLOADER = "reference_downloader"
    DOCX_GENERATION = "docx_generation"
    LITERATURE_REVIEW = "literature_review"
    LIVE_REPORTS = "live_reports"
    REFERENCE_VALIDATION = "reference_validation"


def is_user_visible_workflow(workflow_type: WorkflowRunType) -> bool:
    """Check if a workflow type should be visible to users."""

    return workflow_type not in [WorkflowRunType.DOCX_GENERATION]
