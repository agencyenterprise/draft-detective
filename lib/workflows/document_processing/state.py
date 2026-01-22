from typing import Annotated, List, Literal, Optional

from pydantic import Field

from lib.agents.document_summarizer import DocumentSummary
from lib.agents.models import ChunkWithIndex
from lib.services.docling_models import ChunkToItems
from lib.services.file import FileDocument
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class DocumentProcessingWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for document processing workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_PROCESSING] = Field(
        WorkflowRunType.DOCUMENT_PROCESSING
    )


class DocumentChunk(ChunkWithIndex):
    """Raw document chunk without analysis results."""

    pass


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


def merge_chunks(
    existing: List[DocumentChunk],
    new: List[DocumentChunk],
) -> List[DocumentChunk]:
    """Reducer to upsert chunks by chunk_index.

    This reducer function is used by LangGraph to handle incremental updates
    from parallel chunking operations. Each update overwrites the entry
    with the same chunk_index, allowing updates to existing chunks.
    """
    chunks_by_index = {c.chunk_index: c for c in existing}

    for chunk in new:
        chunks_by_index[chunk.chunk_index] = chunk

    return list(chunks_by_index.values())


class DocumentProcessingState(BaseWorkflowState):
    """State for document processing workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_PROCESSING] = Field(
        WorkflowRunType.DOCUMENT_PROCESSING
    )

    # Inputs
    file: FileDocument
    supporting_files: Optional[List[FileDocument]] = None
    config: DocumentProcessingWorkflowConfig

    # Outputs
    summaries: Annotated[List[FileSummary], merge_summaries] = Field(
        default_factory=list,
        description="List of document summaries for main and supporting files",
    )
    chunks: Annotated[List[DocumentChunk], merge_chunks] = Field(
        default_factory=list, description="Document chunks from main document"
    )
    chunk_to_items: Optional[ChunkToItems] = Field(
        default=None,
        description="Mapping from chunk indices to Docling items/regions for rendering",
    )

    def get_main_summary(self) -> Optional[FileSummary]:
        """Find the summary for the main document."""
        if not self.summaries:
            return None
        return next(
            (s for s in self.summaries if s.file_id == self.file.file_id),
            None,
        )
