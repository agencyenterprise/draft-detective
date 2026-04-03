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
    CANCELLED = "cancelled"


class ReferenceFetchResult(BaseModel):
    """Wrapper for reference fetch results with status tracking"""

    reference_id: str = Field(description="ID of the reference being fetched")
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


def merge_fetch_results(
    existing: List[ReferenceFetchResult],
    new: List[ReferenceFetchResult],
) -> List[ReferenceFetchResult]:
    """Reducer to merge results by reference_id, preserving order.

    This reducer function is used by LangGraph to handle incremental updates
    from parallel fetch operations. Each update overwrites the entry with the
    same reference_id, allowing status transitions from PENDING to COMPLETED/ERROR.
    """
    results_by_id = {r.reference_id: r for r in existing}

    for item in new:
        results_by_id[item.reference_id] = item

    # Return in insertion order (dict preserves order in Python 3.7+)
    return list(results_by_id.values())


class ReferenceDownloaderInputItem(BaseModel):
    """Input item for the reference downloader workflow"""

    reference_id: str = Field(
        description="The ID of the reference from the reference extraction workflow"
    )
    text: str = Field(
        description="The text of the reference to fetch from the internet"
    )


class ReferenceDownloaderWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the reference downloader workflow"""

    type: Literal[WorkflowRunType.REFERENCE_DOWNLOADER] = Field(
        WorkflowRunType.REFERENCE_DOWNLOADER
    )
    references: List[ReferenceDownloaderInputItem] = Field(
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
