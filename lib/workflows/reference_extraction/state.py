"""State definitions for reference extraction workflow."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ReferenceSection(BaseModel):
    """A detected reference/bibliography section in the document."""

    start_offset: int = Field(description="Character offset where section starts")
    end_offset: int = Field(description="Character offset where section ends")


class ExtractedReference(BaseModel):
    """A reference extracted from the document."""

    id: str = Field(description="Unique identifier for this reference")
    text: str = Field(description="The extracted reference text")
    start_line: Optional[int] = Field(
        default=None, description="1-indexed starting line number in the markdown"
    )
    end_line: Optional[int] = Field(
        default=None, description="1-indexed ending line number in the markdown"
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

    # Inputs
    config: ReferenceExtractionConfig
    file_id: str = Field(description="ID of the main document")

    # Outputs
    detected_sections: List[ReferenceSection] = Field(
        default_factory=list, description="Detected reference sections"
    )
    extracted_references: List[ExtractedReference] = Field(
        default_factory=list, description="Extracted references with unique IDs"
    )
    reasoning: str = Field(
        default="",
        description="Step-by-step reasoning describing how references were found and extracted",
    )
