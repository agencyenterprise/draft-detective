from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lib.workflows.agent_messages import AgentMessages
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    ErrorDetails,
    WorkflowRunType,
)
from lib.workflows.reducers import Reducer, upsert_by
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
    result: ReferenceFetchItem | None = Field(
        default=None, description="The fetch result, present on success"
    )
    error: str | None = Field(
        default=None, description="Error message, present on failure"
    )
    error_details: ErrorDetails | None = Field(
        default=None,
        description="Traceback and raw model output behind `error`, for debugging",
    )
    messages: AgentMessages = Field(
        default_factory=list,
        description="LLM conversation messages from the reference fetcher agent invocation.",
    )


# Merges by reference_id so each fetch result replaces its PENDING row.
merge_fetch_results: Reducer[ReferenceFetchResult] = upsert_by(lambda r: r.reference_id)


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
    references: list[ReferenceDownloaderInputItem] | None = Field(
        default=None,
        description=(
            "The references to fetch from the internet. When omitted, the "
            "workflow defaults to every extracted reference that does not yet "
            "have a matched supporting file."
        ),
    )


class ReferenceDownloaderState(BaseWorkflowState):
    """State for the reference downloader workflow"""

    type: Literal[WorkflowRunType.REFERENCE_DOWNLOADER] = Field(
        WorkflowRunType.REFERENCE_DOWNLOADER
    )
    config: ReferenceDownloaderWorkflowConfig = Field(
        description="The configuration for the workflow",
    )
    fetched_references: Annotated[list[ReferenceFetchResult], merge_fetch_results] = (
        Field(
            default_factory=list,
            description="The response from the reference fetcher agent",
        )
    )
    run_reference_ids: list[str] = Field(
        default_factory=list,
        description=(
            "IDs of the references this run fetches. `fetched_references` also "
            "holds earlier runs' results, which this run must not report on."
        ),
    )
