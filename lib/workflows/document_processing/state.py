from typing import Annotated, Dict, List, Literal, Optional

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
    main_document_summary: Optional[DocumentSummary] = Field(
        default=None, description="The summary of the main document"
    )
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = Field(
        default=None,
        description="Dictionary mapping supporting file indices to their summaries",
    )
    chunks: List[DocumentChunk] = Field(
        default_factory=list, description="Document chunks from main document"
    )
    chunk_to_items: Optional[ChunkToItems] = Field(
        default=None,
        description="Mapping from chunk indices to Docling items/regions for rendering",
    )

