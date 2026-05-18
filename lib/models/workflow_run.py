import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import field_serializer, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Enum as SQLModelEnum
from sqlmodel import Field, SQLModel, String

from lib.workflows.models import WorkflowRunType


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


TERMINAL_WORKFLOW_RUN_STATUSES = (
    WorkflowRunStatus.COMPLETED,
    WorkflowRunStatus.CANCELLED,
    WorkflowRunStatus.FAILED,
)


class WorkflowRunFailureReason(str, Enum):
    """Reason a workflow run transitioned to FAILED.

    FAILED is reserved for unrecoverable workflow-level halts; node-level errors
    that the workflow recovers from are still represented via state.errors and
    leave the run in COMPLETED status.
    """

    TIMEOUT = "timeout"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    NO_HEARTBEAT = "no_heartbeat"
    UNHANDLED_EXCEPTION = "unhandled_exception"


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="The unique identifier for the workflow run",
    )
    project_id: Optional[uuid.UUID] = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        description="FK for the project that this workflow run belongs to",
    )
    type: WorkflowRunType = Field(
        sa_column=Column(String(255), nullable=False),
        description="The type of the workflow run",
    )
    langgraph_thread_id: str = Field(sa_column=Column(String(255), nullable=False))
    status: WorkflowRunStatus = Field(
        sa_column=Column(
            SQLModelEnum(WorkflowRunStatus),
            nullable=False,
            default=WorkflowRunStatus.PENDING,
        ),
        description="The status of the workflow run",
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="The timestamp when the workflow run was created",
    )
    last_updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        ),
        description="The timestamp when the workflow run was last updated",
    )
    started_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="The timestamp when the workflow run transitioned to RUNNING",
    )
    completed_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="The timestamp when the workflow run transitioned to COMPLETED or CANCELLED",
    )
    revision: int = Field(
        sa_column=Column(Integer, nullable=False, default=1),
        default=1,
        description="The project revision this workflow run belongs to",
    )
    heartbeat_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Updated on every node entry/exit; used by the reaper to detect stuck runs",
    )
    failure_reason: Optional[WorkflowRunFailureReason] = Field(
        sa_column=Column(
            SQLModelEnum(WorkflowRunFailureReason),
            nullable=True,
        ),
        default=None,
        description="Populated only when status == FAILED",
    )
    failure_message: Optional[str] = Field(
        sa_column=Column(String(2000), nullable=True),
        default=None,
        description="Short human-readable detail of the failure. Populated only when status == FAILED.",
    )
    state_json: Optional[dict[str, Any]] = Field(
        sa_column=Column(JSONB, nullable=True),
        default=None,
        description=(
            "Serialized WorkflowState; written after every node yield. Schema is "
            "the WorkflowState subclass for `type`."
        ),
    )

    @field_validator("type", mode="before")
    @classmethod
    def coerce_type_to_enum(cls, v):
        """Coerce string values from database to WorkflowRunType enum."""
        return _coerce_type_to_enum(v)

    @field_serializer("type")
    def serialize_type(self, value):
        """Ensure type is serialized as enum, converting from string if needed."""
        return _coerce_type_to_enum(value)

    def __repr__(self):
        return f"<WorkflowRun(id={self.id}, langgraph_thread_id={self.langgraph_thread_id})>"


def _coerce_type_to_enum(v: Any):
    """Coerce string values from database to WorkflowRunType enum."""

    if isinstance(v, str):
        try:
            return WorkflowRunType(v)
        except ValueError:
            # Return as-is if not a valid enum value (i.e. deprecated types)
            return v

    return v


# Mark `state_json` as deferred-load by default. Payloads can be multiple MB
# (p99 ≈ 3 MB, max 13 MB observed); hauling them through every SELECT on
# workflow_runs would be a major regression in the reaper, status checks,
# cancel paths, and list endpoints. Callers that actually need state should
# opt in with `select(...).options(undefer(col(WorkflowRun.state_json)))` or
# load it via `hydrate_workflow_run_state(run)` (which triggers a lazy fetch).
#
# Configured here rather than via `Field(sa_column=deferred(...))` because
# SQLModel's Field validator rejects non-Column values for sa_column. Setting
# `strategy_key` post-mapper-init and re-resolving the strategy is the
# documented internal hook SQLAlchemy uses itself; if a future upgrade changes
# the tuple shape, mapper configuration will fail loudly at import time.
_state_json_prop = inspect(WorkflowRun).attrs.state_json
_state_json_prop.strategy_key = (("deferred", True), ("instrument", True))  # type: ignore[attr-defined]
_state_json_prop.strategy = _state_json_prop._get_strategy(  # type: ignore[attr-defined]
    _state_json_prop.strategy_key  # type: ignore[attr-defined]
)
