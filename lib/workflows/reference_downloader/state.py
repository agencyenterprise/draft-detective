from typing import List, Literal, Optional

from pydantic import Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchItem,
)


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
    fetched_references: Optional[List[ReferenceFetchItem]] = Field(
        default=None,
        description="The response from the reference fetcher agent",
    )
    downloaded_references: Optional[List[str | None]] = Field(
        default=None,
        description="The hashes of the files that were downloaded, or None if the download failed. Indexes match the fetched_references list.",
    )
