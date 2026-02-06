from typing import List, Literal

from pydantic import Field

from lib.agents.citation_detector import CitationResponse
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
    file_id: str = Field(default="", description="File ID for backward compatibility")
    config: CitationDetectionConfig

    # Outputs
    citations: List[CitationResponse] = []
