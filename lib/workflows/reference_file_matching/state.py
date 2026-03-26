"""State definitions for reference file matching workflow."""

from enum import Enum
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, model_validator

from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    WorkflowRunType,
)


class MatchSource(str, Enum):
    """How a reference-to-file match was created."""

    # User explicitly uploaded a supporting file for a specific reference via
    # the file upload dialog in the References tab (TUS upload with reference_id metadata).
    MANUAL_UPLOAD = "manual_upload"

    # The ReferenceFileMatching workflow automatically matched a reference to a
    # supporting file that was bulk-uploaded with the project, using embedding
    # similarity and LLM-based matching.
    AUTO_MATCHED = "auto_matched"

    # The ReferenceDownloader workflow found and downloaded the reference source
    # from the web using an AI agent that searches for and retrieves the document.
    AUTO_FETCHED = "auto_fetched"


class ReferenceFileMatch(BaseModel):
    """Links a reference to a matched supporting file."""

    reference_id: str = Field(description="ID of the ExtractedReference")
    file_id: str = Field(description="ID of the matched supporting file")
    source: MatchSource = Field(
        default=MatchSource.AUTO_MATCHED,
        description="How this match was created",
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_is_manual(cls, data: Any) -> Any:
        """Migrate legacy is_manual bool to source enum."""
        if isinstance(data, Dict) and "is_manual" in data and "source" not in data:
            data = dict(data)
            data["source"] = (
                MatchSource.MANUAL_UPLOAD if data.pop("is_manual") else MatchSource.AUTO_MATCHED
            )
        return data


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
