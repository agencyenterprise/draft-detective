from typing import Dict, List, Literal, Optional

from pydantic import Field

from lib.agents.citation_suggester import CitationSuggestionResultWithClaimIndex
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.literature_review import LiteratureReviewResponse
from lib.agents.reference_extractor import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.claim_substantiation.state import DocumentChunk
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class CitationSuggesterWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the citation suggester workflow."""

    type: Literal[WorkflowRunType.CITATION_SUGGESTER] = Field(
        WorkflowRunType.CITATION_SUGGESTER
    )


class CitationSuggesterState(BaseWorkflowState):
    """State for the citation suggester workflow."""

    type: Literal[WorkflowRunType.CITATION_SUGGESTER] = Field(
        WorkflowRunType.CITATION_SUGGESTER
    )
    config: CitationSuggesterWorkflowConfig
    file: FileDocument
    references: List[BibliographyItem] = Field(default_factory=list)
    chunks: List[DocumentChunk] = Field(default_factory=list)
    supporting_files: Optional[List[FileDocument]] = None
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = Field(
        default=None,
        description="Dictionary mapping supporting file indices to their summaries",
    )
    literature_review: Optional[LiteratureReviewResponse] = None
    citation_suggestions: List[CitationSuggestionResultWithClaimIndex] = Field(
        default_factory=list,
        description="Citation suggestions for all chunks and claims",
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[DocumentChunk]:
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])
