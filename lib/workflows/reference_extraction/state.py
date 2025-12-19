"""State definitions for reference extraction workflow."""

from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.reference_extractor import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


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

    config: ReferenceExtractionConfig

    # Inputs (from DOCUMENT_PROCESSING)
    file: FileDocument = Field(description="Main document with markdown populated")
    supporting_files: Optional[List[FileDocument]] = Field(
        default=None, description="Optional supporting documents for matching"
    )

    # Final output
    references: List[BibliographyItem] = Field(
        default_factory=list, description="Extracted bibliography items"
    )

