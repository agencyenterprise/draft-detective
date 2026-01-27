"""State definitions for document processing workflow."""

from typing import List, Literal, Optional

from pydantic import Field

from lib.services.file import FileDocument
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class DocumentProcessingWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for document processing workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_PROCESSING] = Field(
        WorkflowRunType.DOCUMENT_PROCESSING
    )


class DocumentProcessingState(BaseWorkflowState):
    """State for document processing workflow."""

    type: Literal[WorkflowRunType.DOCUMENT_PROCESSING] = Field(
        WorkflowRunType.DOCUMENT_PROCESSING
    )

    config: DocumentProcessingWorkflowConfig
    file: FileDocument
    supporting_files: Optional[List[FileDocument]] = None
