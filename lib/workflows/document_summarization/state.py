"""State definitions for document summarization workflow."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.reducers import Reducer, upsert_by


class DocumentSummarizationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for document summarization workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_SUMMARIZATION] = Field(
        WorkflowRunType.DOCUMENT_SUMMARIZATION
    )


class DocumentSummary(BaseModel):
    title: str = Field(
        description="The title of the document. Suggest a clear, concise title if the document does not have one."
    )
    authors: str = Field(
        description="The authors of the document (if available, otherwise empty string)."
    )
    publication_date: str = Field(
        description="The publication date of the document, or 'Unknown' if not available."
    )
    abstract: str = Field(
        description="The abstract of the document, or 'Unknown' if not available."
    )
    summary: str = Field(
        description=(
            "A ~1000-word miniature version of the document (roughly 900–1100 words) "
            "that focuses on the main argument of the work. It should read like a "
            "compressed research report: clearly stating the central question or problem, "
            "the main claim/argument, the essential methods or analytical framework, the "
            "critical results, and how these results support the argument, while omitting "
            "tangential or overly detailed implementation information."
        )
    )


class FileSummary(DocumentSummary):
    """Summary of a file. Extends DocumentSummary to include the file ID to match the summary to the file."""

    file_id: str = Field(description="The ID of the file")


# Upserts by file_id so each parallel summarization replaces that file's summary.
merge_summaries: Reducer[FileSummary] = upsert_by(lambda s: s.file_id)


class DocumentSummarizationState(BaseWorkflowState):
    """State for document summarization workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_SUMMARIZATION] = Field(
        WorkflowRunType.DOCUMENT_SUMMARIZATION
    )

    # Inputs
    config: DocumentSummarizationWorkflowConfig
    main_file_id: str = Field(
        description="ID of the main document to summarize (full content used)",
    )
    supporting_file_ids: list[str] = Field(
        default_factory=list,
        description="IDs of supporting documents to summarize (truncated content used)",
    )

    # Outputs
    summaries: Annotated[list[FileSummary], merge_summaries] = Field(
        default_factory=list,
        description="List of document summaries for main and supporting files",
    )
