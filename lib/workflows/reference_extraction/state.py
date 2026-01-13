"""State definitions for reference extraction workflow."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from lib.agents.document_summarizer import DocumentSummary
from lib.models.bibliography_item import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


class ReferenceSection(BaseModel):
    """A detected reference/bibliography section in the document."""

    start_offset: int = Field(description="Character offset where section starts")
    end_offset: int = Field(description="Character offset where section ends")


class ReferenceExtractionConfig(BaseWorkflowConfig):
    """Configuration for reference extraction workflow."""

    type: Literal[WorkflowRunType.REFERENCE_EXTRACTION] = Field(
        default=WorkflowRunType.REFERENCE_EXTRACTION
    )


class ReferenceExtractionState(BaseWorkflowState):
    """State for reference extraction workflow."""

    type: Literal[WorkflowRunType.REFERENCE_EXTRACTION] = Field(
        default=WorkflowRunType.REFERENCE_EXTRACTION
    )

    # Inputs
    config: ReferenceExtractionConfig
    file_id: str = Field(description="ID of the main document")
    supporting_file_ids: List[str] = Field(
        description="IDs of the supporting documents"
    )

    # Outputs
    detected_sections: List[ReferenceSection] = Field(
        default_factory=list, description="Detected reference sections"
    )
    extracted_reference_texts: List[str] = Field(
        default_factory=list, description="Raw extracted reference texts"
    )
    references: List[BibliographyItem] = Field(
        default_factory=list, description="Extracted bibliography items"
    )
