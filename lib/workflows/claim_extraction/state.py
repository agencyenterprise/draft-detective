from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.claim_categorizer import ClaimCategorizationResponseWithClaimIndex
from lib.agents.claim_extractor import ClaimResponseWithChunkIndex
from lib.agents.document_summarizer import DocumentSummary
from lib.workflows.document_processing.state import DocumentChunk
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimExtractionWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim extraction workflow"""

    type: Literal[WorkflowRunType.CLAIM_EXTRACTION] = Field(
        WorkflowRunType.CLAIM_EXTRACTION
    )
    target_chunk_indices: Optional[List[int]] = Field(
        default=None,
        description="Specific chunk indices to process (None = process all chunks)",
    )


class ClaimExtractionState(BaseWorkflowState):
    """State for claim extraction workflow."""

    type: Literal[WorkflowRunType.CLAIM_EXTRACTION] = Field(
        WorkflowRunType.CLAIM_EXTRACTION
    )

    # Inputs
    config: ClaimExtractionWorkflowConfig

    # Document processing artifacts
    chunks: List[DocumentChunk] = Field(
        default_factory=list, description="Document chunks from main document"
    )
    main_document_summary: Optional[DocumentSummary] = Field(
        default=None, description="The summary of the main document"
    )

    # Outputs
    claims: List[ClaimResponseWithChunkIndex] = Field(
        default_factory=list,
        description="List of extracted claims with chunk indices",
    )
    claim_categories: List[ClaimCategorizationResponseWithClaimIndex] = Field(
        default_factory=list,
        description="List of claim categorizations with claim indices",
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[DocumentChunk]:
        """Get all chunks for a given paragraph index."""
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        """Get the full paragraph text for a given paragraph index."""
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])
