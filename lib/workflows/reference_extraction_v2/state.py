"""State definitions for reference extraction v2 workflow."""

from typing import List, Literal, Optional

from pydantic import Field

from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


class ReferenceExtractionV2Config(BaseWorkflowConfig):
    """Configuration for reference extraction v2 workflow."""

    type: Literal[WorkflowRunType.REFERENCE_EXTRACTION_V2] = Field(
        default=WorkflowRunType.REFERENCE_EXTRACTION_V2
    )


class ReferenceExtractionV2State(BaseWorkflowState):
    """State for reference extraction v2 workflow."""

    type: Literal[WorkflowRunType.REFERENCE_EXTRACTION_V2] = Field(
        default=WorkflowRunType.REFERENCE_EXTRACTION_V2
    )

    # Inputs
    config: ReferenceExtractionV2Config
    file_id: str = Field(description="ID of the main document")

    # Outputs
    reasoning: Optional[str] = Field(
        default=None, description="Agent reasoning explaining how references were found"
    )
    references: List[str] = Field(
        default_factory=list, description="Extracted reference texts"
    )
