"""State definitions for document summarization workflow."""

from typing import Annotated, List, Literal

from pydantic import Field

from lib.agents.document_summarizer import DocumentSummary
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class DocumentSummarizationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for document summarization workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_SUMMARIZATION] = Field(
        WorkflowRunType.DOCUMENT_SUMMARIZATION
    )


class FileSummary(DocumentSummary):
    """Summary of a file. Extends DocumentSummary to include the file ID to match the summary to the file."""

    file_id: str = Field(description="The ID of the file")


def merge_summaries(
    existing: List[FileSummary],
    new: List[FileSummary],
) -> List[FileSummary]:
    """Reducer to upsert summaries by file_id.

    This reducer function is used by LangGraph to handle incremental updates
    from parallel summarization operations. Each update overwrites the entry
    with the same file_id, allowing updates to existing summaries.
    """
    summaries_by_file_id = {s.file_id: s for s in existing}

    for item in new:
        summaries_by_file_id[item.file_id] = item

    return list(summaries_by_file_id.values())


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
    supporting_file_ids: List[str] = Field(
        default_factory=list,
        description="IDs of supporting documents to summarize (truncated content used)",
    )

    # Outputs
    summaries: Annotated[List[FileSummary], merge_summaries] = Field(
        default_factory=list,
        description="List of document summaries for main and supporting files",
    )
