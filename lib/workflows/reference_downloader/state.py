from enum import Enum
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchItem,
)


class ReferenceFetchStatus(str, Enum):
    """Status of a reference fetch operation"""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"


class ReferenceFetchResult(BaseModel):
    """Wrapper for reference fetch results with status tracking"""

    index: int = Field(description="Index of this reference in the input list")
    input_reference: str = Field(description="The original input reference")
    status: ReferenceFetchStatus = Field(
        default=ReferenceFetchStatus.PENDING,
        description="Current status of this reference fetch",
    )
    result: Optional[ReferenceFetchItem] = Field(
        default=None, description="The fetch result, present on success"
    )
    error: Optional[str] = Field(
        default=None, description="Error message, present on failure"
    )

    @property
    def is_error(self) -> bool:
        return self.status == ReferenceFetchStatus.ERROR


def merge_fetch_results(
    existing: List[ReferenceFetchResult],
    new: List[ReferenceFetchResult],
) -> List[ReferenceFetchResult]:
    """Reducer to merge results by index, preserving order.

    This reducer function is used by LangGraph to handle incremental updates
    from parallel fetch operations. Each update overwrites the entry at the
    same index, allowing status transitions from PENDING to COMPLETED/ERROR.
    """
    results_by_index = {r.index: r for r in existing}

    for item in new:
        results_by_index[item.index] = item

    # Return sorted by index to maintain consistent order
    return [results_by_index[i] for i in sorted(results_by_index.keys())]


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
    fetched_references: Annotated[List[ReferenceFetchResult], merge_fetch_results] = (
        Field(
            default_factory=list,
            description="The response from the reference fetcher agent",
        )
    )
