from enum import Enum, StrEnum
from operator import add
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

from lib.agents.models import ClaimCategory


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
    domain: Optional[str] = Field(
        default=None, description="Domain context for more accurate analysis"
    )
    target_audience: Optional[str] = Field(
        default=None, description="Target audience context for analysis"
    )
    publication_date: Optional[str] = Field(
        default=None, description="Publication date of the document (YYYY-MM-DD format)"
    )

    @classmethod
    def requires_api_key(cls) -> bool:
        """
        Whether this workflow requires an OpenAI API key.

        Defaults to True for safety. Workflows that don't use LLMs
        (e.g., data manipulation only) should override this to return False.
        """
        return True


class WorkflowRunType(str, Enum):
    DOCUMENT_PROCESSING = "document_processing"
    REFERENCE_EXTRACTION = "reference_extraction"
    FOOTNOTE_EXTRACTION = "footnote_extraction"
    CLAIM_EXTRACTION = "claim_extraction"
    CITATION_DETECTION = "citation_detection"
    METHODOLOGICAL_ALIGNMENT = "methodological_alignment"
    REFERENCE_DOWNLOADER = "reference_downloader"
    DOCX_GENERATION = "docx_generation"
    LITERATURE_REVIEW = "literature_review"
    LIVE_REPORTS = "live_reports"
    REFERENCE_VALIDATION = "reference_validation"
    CITATION_SUGGESTER = "citation_suggester"
    RESULTS_EXTRACTION = "results_extraction"
    INFERENCE_VALIDATION = "inference_validation"
    CLAIM_REFERENCE_VALIDATION = "claim_reference_validation"


def is_user_visible_workflow(workflow_type: WorkflowRunType) -> bool:
    """
    Check if a workflow type should be visible to users in the workflow list.
    Uses the is_internal flag from each workflow's manifest.
    """
    from lib.workflows.registry import _workflow_manifest_registry

    manifest = _workflow_manifest_registry.get(workflow_type)
    if manifest is None:
        return False
    return not manifest.is_internal


class SeverityEnum(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def sort_index(self) -> int:
        return {
            self.NONE: 0,
            self.LOW: 1,
            self.MEDIUM: 2,
            self.HIGH: 3,
        }[self]


class DocumentIssue(BaseModel):
    title: str = Field(description="The title of the issue")
    description: str = Field(description="The description of the issue")
    severity: SeverityEnum = Field(description="The severity of the issue")
    chunk_index: Optional[int] = Field(
        description="The index of the chunk that contains the issue", default=None
    )
    claim_index: Optional[int] = Field(
        description="The index of the claim that contains the issue", default=None
    )
    claim_category: Optional[ClaimCategory] = Field(
        description="The category of the claim that contains the issue", default=None
    )
