"""State definitions for reference file matching workflow."""

from typing import List, Literal

from pydantic import BaseModel, Field

from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


class ReferenceFileMatch(BaseModel):
    """Links a reference to a matched supporting file."""

    reference_id: str = Field(description="ID of the ExtractedReference")
    file_id: str = Field(description="ID of the matched supporting file")
    is_manual: bool = Field(
        default=False,
        description="Whether this match was manually created by a user",
    )


class ReferenceFileMatchingConfig(BaseWorkflowConfig):
    """Configuration for reference file matching workflow."""

    type: Literal[WorkflowRunType.REFERENCE_FILE_MATCHING] = Field(
        default=WorkflowRunType.REFERENCE_FILE_MATCHING
    )


class ReferenceFileMatchingState(BaseWorkflowState):
    """State for reference file matching workflow."""

    type: Literal[WorkflowRunType.REFERENCE_FILE_MATCHING] = Field(
        default=WorkflowRunType.REFERENCE_FILE_MATCHING
    )

    # Inputs
    config: ReferenceFileMatchingConfig
    file_id: str = Field(description="ID of the main document")
    supporting_file_ids: List[str] = Field(
        default_factory=list, description="IDs of the supporting documents"
    )

    # Outputs - only matched references have entries here
    matches: List[ReferenceFileMatch] = Field(
        default_factory=list,
        description="List of matches between references and supporting files",
    )
