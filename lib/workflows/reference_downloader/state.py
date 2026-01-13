from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchItem,
)


class ReferenceFetchResult(BaseModel):
    """Wrapper for reference fetch results that handles both success and error cases"""

    input_reference: str = Field(
        description="The original input reference (always present)"
    )
    result: Optional[ReferenceFetchItem] = Field(
        default=None, description="The fetch result, present on success"
    )
    error: Optional[str] = Field(
        default=None, description="Error message, present on failure"
    )

    @property
    def is_error(self) -> bool:
        return self.error is not None


class ReferenceDownloaderWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the reference downloader workflow"""

    type: Literal[WorkflowRunType.REFERENCE_DOWNLOADER] = Field(
        WorkflowRunType.REFERENCE_DOWNLOADER
    )
    references: List[str] = Field(
        description="The references to fetch from the internet",
    )


class ReferenceDownloaderState(BaseWorkflowState):
    """State for the reference downloader workflow"""

    type: Literal[WorkflowRunType.REFERENCE_DOWNLOADER] = Field(
        WorkflowRunType.REFERENCE_DOWNLOADER
    )
    config: ReferenceDownloaderWorkflowConfig = Field(
        description="The configuration for the workflow",
    )
    fetched_references: Optional[List[ReferenceFetchResult]] = Field(
        default=None,
        description="The response from the reference fetcher agent",
    )
