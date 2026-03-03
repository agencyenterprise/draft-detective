"""State definitions for abbreviation scan workflow."""

from typing import List, Literal

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class AbbreviationItemV1(BaseModel):
    """Item representing an abbreviation/acronym and its definition."""

    abbr: str = Field(description="The acronym/abbreviation text, e.g. AI, RAND, NATO")
    definition: str = Field(
        default="",
        description="Full definition if available, e.g. Artificial Intelligence",
    )
    context: str = Field(
        description="Text content of the chunk where the abbreviation was found/defined"
    )
    is_definition: bool = Field(
        description="True if found as a definition like 'Definition (ABBR)'"
    )
    chunk_index: int = Field(
        description="0-based chunk index where this abbreviation was found"
    )


class AbbreviationScanWorkflowConfig(BaseWorkflowConfig):
    """Configuration for abbreviation scan workflow."""

    type: Literal[WorkflowRunType.ABBREVIATION_SCAN] = Field(
        default=WorkflowRunType.ABBREVIATION_SCAN
    )

    @classmethod
    def requires_api_key(cls) -> bool:
        return False


class AbbreviationScanState(BaseWorkflowState):
    """State for abbreviation scan workflow."""

    type: Literal[WorkflowRunType.ABBREVIATION_SCAN] = Field(
        default=WorkflowRunType.ABBREVIATION_SCAN
    )

    # Inputs
    config: AbbreviationScanWorkflowConfig
    file_id: str = Field(description="ID of the main document")

    # Outputs
    abbreviations: List[AbbreviationItemV1] = Field(
        default_factory=list,
        description="Unique abbreviations found in the document",
    )
