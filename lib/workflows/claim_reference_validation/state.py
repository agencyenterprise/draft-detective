from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.claim_verifier import ClaimSubstantiationResultWithClaimIndex
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.models import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.base import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimReferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim reference validation workflow"""

    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION
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


class ClaimReferenceValidationState(BaseWorkflowState):
    """State for the claim reference validation workflow."""

    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    )
    config: ClaimReferenceValidationWorkflowConfig
    file: FileDocument
    supporting_files: Optional[List[FileDocument]] = None
    chunks: List[AnalyzedChunk] = Field(default_factory=list)
    references: List[BibliographyItem] = Field(default_factory=list)
    main_document_summary: Optional[DocumentSummary] = Field(
        default=None, description="The summary of the main document"
    )
    substantiations: List[ClaimSubstantiationResultWithClaimIndex] = Field(
        default_factory=list,
        description="Claim substantiation results indexed by chunk_index and claim_index",
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[AnalyzedChunk]:
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])
