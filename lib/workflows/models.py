import hashlib
from enum import Enum, StrEnum
from operator import add
from typing import Annotated, List, Optional, Self

from pydantic import BaseModel, Field, model_validator


class WorkflowCancelledError(Exception):
    """Raised when a workflow has been cancelled. Propagates through LangGraph without being converted to a WorkflowError."""

    pass


class DependencyWaitTimeoutError(Exception):
    """Raised when wait_for_dependencies exceeds DEPENDENCY_WAIT_TIMEOUT.

    Indicates an upstream dependency is stuck (typically itself orphaned in
    RUNNING). The dependent run should be marked FAILED with
    failure_reason=dependency_timeout.
    """

    pass


class WorkflowErrorSeverity(StrEnum):
    """Whether an error compromised the run's output.

    `ERROR` means work was lost: the run's results are incomplete and the user
    should retry. `WARNING` means the failure was handled — the affected step
    recovered usable output — so the run still counts as completed and the
    message is informational.
    """

    ERROR = "error"
    WARNING = "warning"


class ErrorDetails(BaseModel):
    """Diagnostic payload captured from a caught exception.

    Persisted alongside the human-readable error message so failures can be
    debugged from the database alone, without needing the server logs of the
    run that produced them. Every field is optional: older persisted state
    predates this model, and not every exception carries model output.
    """

    error_type: Optional[str] = Field(
        default=None,
        description="Class name of the exception that was caught, e.g. 'StructuredOutputValidationError'.",
    )
    traceback: Optional[str] = Field(
        default=None,
        description="Formatted traceback, including chained causes. Truncated if very long.",
    )
    raw_model_output: Optional[str] = Field(
        default=None,
        description="Raw text the LLM returned, when the exception carried it. Truncated if very long.",
    )
    llm_metadata: Optional[dict] = Field(
        default=None,
        description="Response metadata from the failing LLM call (model name, finish/stop reason, token usage).",
    )


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
    severity: WorkflowErrorSeverity = Field(
        default=WorkflowErrorSeverity.ERROR,
        description=(
            "Whether this error cost the run part of its output ('error') or was "
            "recovered from and is informational ('warning'). Errors persisted "
            "before this field existed read as 'error'."
        ),
    )
    details: Optional[ErrorDetails] = Field(
        default=None,
        description="Diagnostic details (traceback, raw model output, LLM metadata) for debugging this error.",
    )


class BaseWorkflowState(BaseModel):
    """Base model for all workflow states."""

    errors: Annotated[List[WorkflowError], add] = Field(
        default_factory=list,
        description="Errors that occurred during the workflow execution.",
    )


class BaseWorkflowConfig(BaseModel):
    """Base model for all workflow configs."""

    project_id: str = Field(
        description="The ID of the project that this workflow run should be associated with",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="The OpenAI API key to use for this workflow execution",
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


class WorkflowGate(str, Enum):
    """A consent a user must give, per project revision, before a gated
    workflow may run.

    Manifests declare the gates they need in ``WorkflowManifest.gates``. A run
    started while one of its gates is unsatisfied is held in
    ``WorkflowRunStatus.AWAITING_APPROVAL`` until the gate is approved for the
    project's revision (see ``lib.services.workflow_gates``).
    """

    # The user has looked over the reference-to-source-file matching and is
    # happy for Claim Reference Validation to read the sources as matched.
    REFERENCE_REVIEW = "reference_review"


class WorkflowRunType(str, Enum):
    DOCUMENT_PROCESSING = "document_processing"
    DOCUMENT_SUMMARIZATION = "document_summarization"
    REFERENCE_EXTRACTION = "reference_extraction"
    REFERENCE_FILE_MATCHING = "reference_file_matching"
    METHODOLOGICAL_ALIGNMENT = "methodological_alignment"
    REFERENCE_DOWNLOADER = "reference_downloader"
    LITERATURE_REVIEW_V2 = "literature_review_v2"
    LIVE_REPORTS_V2 = "live_reports_v2"
    REFERENCE_VALIDATION_V2 = "reference_validation_v2"
    RESULTS_EXTRACTION = "results_extraction"
    INFERENCE_VALIDATION_V2 = "inference_validation_v2"
    CLAIM_REFERENCE_VALIDATION_V2 = "claim_reference_validation_v2"
    ABBREVIATION_SCAN_V2 = "abbreviation_scan_v2"
    ADVOCACY_TONE_V2 = "advocacy_tone_v2"
    ABOUT_THIS_GER = "about_this_ger"
    REVIEWER_2 = "reviewer_2"
    DOCUMENT_STRUCTURE = "document_structure"
    FIGURES_TABLES_CHECK = "figures_tables_check"
    RECOMMENDATION_CHECK = "recommendation_check"
    REVISION_PLANNING_SUMMARY = "revision_planning_summary"
    REVIEWER_RESPONSE_MEMOS = "reviewer_response_memos"
    REVIEWER_COVERAGE_REPORT = "reviewer_coverage_report"


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
        description="A unique identifier for the issue, generated as a hash of type + title + description + severity + chunk_indices.",
    )
    title: str = Field(description="The title of the issue")
    description: str = Field(
        description="A short description of the issue, enough to understand the issue at a glance. Can be markdown."
    )
    long_description: Optional[str] = Field(
        description="A long description of the issue, including all the details necessary to understand the issue in detail. Can be markdown.",
        default=None,
    )
    suggested_action: Optional[str] = Field(
        default=None,
        description=(
            "A direct, concise recommendation to the author on what to do to resolve "
            "this issue. Markdown is supported."
        ),
    )
    severity: SeverityEnum = Field(description="The severity of the issue")
    type: WorkflowRunType = Field(
        description="The workflow type that generated this issue"
    )
    chunk_indices: Optional[List[int]] = Field(
        description="The indices of all chunks that contain the issue",
        default=None,
    )
    start_line: Optional[int] = Field(
        description="1-indexed start line of the issue in the main document markdown",
        default=None,
    )
    end_line: Optional[int] = Field(
        description="1-indexed end line of the issue in the main document markdown",
        default=None,
    )

    @model_validator(mode="after")
    def generate_id(self) -> Self:
        """Generate a deterministic ID based on issue content, only if not already set."""

        if self.id:
            return self

        hash_input = (
            f"{self.type.value}|{self.title}|{self.description}|"
            f"{self.severity.value}|{self.chunk_indices}|"
            f"{self.start_line}|{self.end_line}"
        )
        self.id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return self
