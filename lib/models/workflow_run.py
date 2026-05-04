import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import field_serializer, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
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
