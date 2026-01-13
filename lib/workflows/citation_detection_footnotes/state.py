from typing import List, Literal

from pydantic import Field

from lib.agents.citation_detector import CitationResponseWithChunkIndex
from lib.models.bibliography_item import BibliographyItem
from lib.models.footnote_item import FootnoteItem
from lib.services.file import FileDocument
from lib.workflows.document_processing.state import DocumentChunk
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class CitationDetectionFootnotesConfig(BaseWorkflowConfig):
    """Configuration model for citation detection with footnotes workflow."""

    type: Literal[WorkflowRunType.CITATION_DETECTION_FOOTNOTES] = Field(
        WorkflowRunType.CITATION_DETECTION_FOOTNOTES
    )


class CitationDetectionFootnotesState(BaseWorkflowState):
    """State for citation detection with footnotes workflow."""

    type: Literal[WorkflowRunType.CITATION_DETECTION_FOOTNOTES] = Field(
        WorkflowRunType.CITATION_DETECTION_FOOTNOTES
    )

    # Inputs
    file: FileDocument
    config: CitationDetectionFootnotesConfig
    chunks: List[DocumentChunk] = []
    references: List[BibliographyItem] = []
    footnotes: List[FootnoteItem] = []

    # Outputs
    citations: List[CitationResponseWithChunkIndex] = []
