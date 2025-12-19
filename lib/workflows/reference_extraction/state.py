"""State definitions for reference extraction workflow."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from lib.agents.models import ChunkWithIndex
from lib.agents.reference_extractor import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


class ReferenceSection(BaseModel):
    """Detected reference section in document."""

    section_type: str = Field(
        description="Type of section (bibliography, footnotes, appendix_references)"
    )
    start_chunk_index: int = Field(description="Starting chunk index of section")
    end_chunk_index: Optional[int] = Field(
        default=None, description="Ending chunk index (None if goes to end of document)"
    )
    confidence: float = Field(
        description="Confidence score for section detection (0-1)"
    )
    section_header: str = Field(description="Detected section header text")


class ReferenceExtractionConfig(BaseWorkflowConfig):
    """Configuration for reference extraction workflow."""

    type: Literal[WorkflowRunType.REFERENCE_EXTRACTION] = Field(
        default=WorkflowRunType.REFERENCE_EXTRACTION
    )

    # Windowing configuration
    window_size: int = Field(
        default=10, description="Number of chunks per extraction window"
    )
    overlap_size: int = Field(
        default=3, description="Number of overlapping chunks between windows"
    )

    # Deduplication configuration
    fuzzy_threshold: float = Field(
        default=0.85,
        description="Similarity threshold for fuzzy matching (0-1)",
    )

    # Supporting document configuration
    truncate_supporting_docs_at: int = Field(
        default=1000,
        description="Character limit for supporting document content in prompts",
    )


class ReferenceExtractionState(BaseWorkflowState):
    """State for reference extraction workflow."""

    type: Literal[WorkflowRunType.REFERENCE_EXTRACTION] = Field(
        default=WorkflowRunType.REFERENCE_EXTRACTION
    )

    config: ReferenceExtractionConfig

    # Inputs (from DOCUMENT_PROCESSING)
    file: FileDocument = Field(description="Main document with markdown populated")
    chunks: List[ChunkWithIndex] = Field(
        default_factory=list, description="Document chunks for section detection"
    )
    supporting_files: Optional[List[FileDocument]] = Field(
        default=None, description="Optional supporting documents for matching"
    )

    # Intermediate outputs
    detected_sections: List[ReferenceSection] = Field(
        default_factory=list, description="Detected reference sections"
    )

    # Final output
    references: List[BibliographyItem] = Field(
        default_factory=list, description="Extracted bibliography items"
    )

