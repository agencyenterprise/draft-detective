from typing import List, Literal

from pydantic import Field

from lib.agents.citation_detector import (
    CitationResponseWithChunkIndex,
)
from lib.models.bibliography_item import BibliographyItem
from lib.models.footnote_item import FootnoteItem
from lib.services.file import FileDocument
from lib.workflows.document_processing.state import DocumentChunk
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class CitationDetectionConfig(BaseWorkflowConfig):
    """Configuration model for citation detection workflow"""

    type: Literal[WorkflowRunType.CITATION_DETECTION] = Field(
        WorkflowRunType.CITATION_DETECTION
    )


class CitationDetectionState(BaseWorkflowState):
    """State for citation detection workflow."""

    type: Literal[WorkflowRunType.CITATION_DETECTION] = Field(
        WorkflowRunType.CITATION_DETECTION
    )

    # Inputs
    file_id: str
    config: CitationDetectionConfig
    chunks: List[DocumentChunk] = []
    references: List[BibliographyItem] = []
    footnotes: List[FootnoteItem] = []

    # Outputs
    citations: List[CitationResponseWithChunkIndex] = []
