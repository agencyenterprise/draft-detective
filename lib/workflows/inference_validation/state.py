from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.document_summarizer import DocumentSummary
from lib.agents.inference_validator import InferenceValidationResponseWithClaimIndex
from lib.services.file import FileDocument
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.base import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class InferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the inference validation workflow."""

    type: Literal[WorkflowRunType.INFERENCE_VALIDATION] = Field(
        WorkflowRunType.INFERENCE_VALIDATION
    )
    domain: Optional[str] = Field(
        default=None, description="Domain context for more accurate analysis"
    )
    target_audience: Optional[str] = Field(
        default=None, description="Target audience context for analysis"
    )


class InferenceValidationState(BaseWorkflowState):
    """State for the inference validation workflow."""

    type: Literal[WorkflowRunType.INFERENCE_VALIDATION] = Field(
        WorkflowRunType.INFERENCE_VALIDATION
    )
    config: InferenceValidationWorkflowConfig
    file: FileDocument
    chunks: List[AnalyzedChunk] = Field(default_factory=list)
    main_document_summary: Optional[DocumentSummary] = Field(
        default=None, description="The summary of the main document"
    )
    inference_validations: List[InferenceValidationResponseWithClaimIndex] = Field(
        default_factory=list
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[AnalyzedChunk]:
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])
