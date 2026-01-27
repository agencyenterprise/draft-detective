from typing import Annotated, List, Literal, Optional

from pydantic import Field

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
    chunks: Annotated[List[DocumentChunk], merge_chunks] = Field(
        default_factory=list, description="Document chunks from main document"
    )
    chunk_to_items: Optional[ChunkToItems] = Field(
        default=None,
        description="Mapping from chunk indices to Docling items/regions for rendering",
    )
