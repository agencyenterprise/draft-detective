"""State definitions for footnote extraction workflow."""

from typing import List, Literal

from pydantic import BaseModel, Field

from lib.models.footnote_item import FootnoteItem
from lib.services.file import FileDocument
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


class FootnoteSection(BaseModel):
    """A detected footnote section in the document."""

    start_offset: int = Field(description="Character offset where section starts")
    end_offset: int = Field(description="Character offset where section ends")


class FootnoteExtractionConfig(BaseWorkflowConfig):
    """Configuration for footnote extraction workflow."""

    type: Literal[WorkflowRunType.FOOTNOTE_EXTRACTION] = Field(
        default=WorkflowRunType.FOOTNOTE_EXTRACTION
    )


class FootnoteExtractionState(BaseWorkflowState):
    """State for footnote extraction workflow."""

    type: Literal[WorkflowRunType.FOOTNOTE_EXTRACTION] = Field(
        default=WorkflowRunType.FOOTNOTE_EXTRACTION
    )

    config: FootnoteExtractionConfig

    # Input (from DOCUMENT_PROCESSING)
    file: FileDocument = Field(description="Main document with markdown populated")

    # Intermediate outputs
    detected_sections: List[FootnoteSection] = Field(
        default_factory=list, description="Detected footnote sections"
    )

    # Final output
    footnotes: List[FootnoteItem] = Field(
        default_factory=list, description="Extracted footnote items"
    )
