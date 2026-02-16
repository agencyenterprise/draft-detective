import hashlib
from enum import Enum, StrEnum
from operator import add
from typing import Annotated, List, Optional, Self

from pydantic import BaseModel, Field, model_validator


class ClaimExtractionVersion(str, Enum):
    """Version selector for claim extraction pipeline."""

    V1 = "v1"
    V2 = "v2"


class WorkflowError(BaseModel):
    """Error object for the overall workflow or specific chunks."""

    chunk_index: Optional[int] = Field(
        default=None,
        description="The index of the chunk that caused the error. This is None if the error occurred before the chunk was processed or in the overall workflow (not chunk-related).",
    )
    task_name: str = Field(description="The name of the task that caused the error.")
    error: str = Field(description="The error message.")
    workflow_run_id: Optional[str] = Field(
        default=None,
        description="The workflow run ID when this error occurred. Used to filter errors to current run only.",
    )


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
    claim_extraction_version: ClaimExtractionVersion = Field(
        default=ClaimExtractionVersion.V2,
        description="Which claim extraction pipeline to use (v1 or v2)",
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
    CHUNK_SPLITTING = "chunk_splitting"
    DOCUMENT_SUMMARIZATION = "document_summarization"
    REFERENCE_EXTRACTION = "reference_extraction"
    REFERENCE_FILE_MATCHING = "reference_file_matching"
    HUMAN_APPROVAL = "human_approval"
    FOOTNOTE_EXTRACTION = "footnote_extraction"
    CLAIM_EXTRACTION = "claim_extraction"
    CLAIM_EXTRACTION_V2 = "claim_extraction_v2"
    CITATION_DETECTION = "citation_detection"
    METHODOLOGICAL_ALIGNMENT = "methodological_alignment"
    REFERENCE_DOWNLOADER = "reference_downloader"
    LITERATURE_REVIEW = "literature_review"
    LIVE_REPORTS = "live_reports"
    REFERENCE_VALIDATION = "reference_validation"
    CITATION_SUGGESTER = "citation_suggester"
    RESULTS_EXTRACTION = "results_extraction"
    INFERENCE_VALIDATION = "inference_validation"
    INFERENCE_VALIDATION_V2 = "inference_validation_v2"
    CLAIM_REFERENCE_VALIDATION = "claim_reference_validation"
    ABBREVIATION_SCAN = "abbreviation_scan"
    ADVOCACY_TONE = "advocacy_tone"
    ABOUT_AUTHORS = "about_authors"
    ABOUT_THIS = "about_this"


def is_user_visible_workflow(workflow_type: WorkflowRunType) -> bool:
    """
    Check if a workflow type should be visible to users in the workflow list.
    Uses the is_internal flag from each workflow's manifest.
    """
    from lib.workflows.registry import get_all_manifests

    manifest = get_all_manifests().get(workflow_type)
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
    id: str = Field(
        default="",
        description="A unique identifier for the issue, generated as a hash of type + title + description + severity + chunk_index + chunk_indices.",
    )
    title: str = Field(description="The title of the issue")
    description: str = Field(
        description="A short description of the issue, enough to understand the issue at a glance. Can be markdown."
    )
    long_description: Optional[str] = Field(
        description="A long description of the issue, including all the details necessary to understand the issue in detail. Can be markdown.",
        default=None,
    )
    severity: SeverityEnum = Field(description="The severity of the issue")
    type: WorkflowRunType = Field(
        description="The workflow type that generated this issue"
    )
    chunk_index: Optional[int] = Field(
        description="The index of the chunk that contains the issue (deprecated, use chunk_indices)",
        default=None,
    )
    chunk_indices: Optional[List[int]] = Field(
        description="The indices of all chunks that contain the issue",
        default=None,
    )

    @model_validator(mode="after")
    def generate_id(self) -> Self:
        """Generate a deterministic ID based on issue content, only if not already set."""

        if self.id:
            return self

        hash_input = (
            f"{self.type.value}|{self.title}|{self.description}|"
            f"{self.severity.value}|{self.chunk_index}|{self.chunk_indices}"
        )
        self.id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return self
