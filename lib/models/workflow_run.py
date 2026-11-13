import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    inspect,
    text,
)
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
    # Waiting on a user to approve a gate (see WorkflowManifest.gates); not scheduled.
    AWAITING_APPROVAL = "awaiting_approval"


TERMINAL_WORKFLOW_RUN_STATUSES = (
    WorkflowRunStatus.COMPLETED,
    WorkflowRunStatus.CANCELLED,
    WorkflowRunStatus.FAILED,
)

# Statuses of a run that has not finished: scheduled and waiting on
# dependencies, executing, or awaiting a user's approval.
ACTIVE_WORKFLOW_RUN_STATUSES = (
    WorkflowRunStatus.PENDING,
    WorkflowRunStatus.RUNNING,
    WorkflowRunStatus.AWAITING_APPROVAL,
)

# Statuses of a run that has not started yet. Per project, revision and type
# there is at most one such run (and at most one RUNNING run), unless the
# workflow runs independently: see the unique indexes on WorkflowRun.
WAITING_WORKFLOW_RUN_STATUSES = (
    WorkflowRunStatus.PENDING,
    WorkflowRunStatus.AWAITING_APPROVAL,
)


class WorkflowRunFailureReason(str, Enum):
    """Reason a workflow run transitioned to FAILED.

    FAILED is reserved for unrecoverable workflow-level halts; node-level errors
    that the workflow recovers from are still represented via state.errors and
    leave the run in COMPLETED status.
    """

    TIMEOUT = "timeout"
    # Written by the dependency wait the job queue replaced; kept so old rows load.
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    NO_HEARTBEAT = "no_heartbeat"
    UNHANDLED_EXCEPTION = "unhandled_exception"


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        # One RUNNING and one waiting run per project, revision and type: a
        # start joins the waiting run instead of adding another (see
        # lib.services.workflow_runs.start). Independent runs are exempt.
        Index(
            "uq_workflow_runs_one_running",
            "project_id",
            "revision",
            "type",
            unique=True,
            postgresql_where=text("status = 'RUNNING' AND NOT independent_run"),
        ),
        Index(
            "uq_workflow_runs_one_waiting",
            "project_id",
            "revision",
            "type",
            unique=True,
            postgresql_where=text(
                "status IN ('PENDING', 'AWAITING_APPROVAL') AND NOT independent_run"
            ),
        ),
    )

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="The unique identifier for the workflow run",
    )
    project_id: uuid.UUID | None = Field(
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
    started_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="The timestamp when the workflow run transitioned to RUNNING",
    )
    completed_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="The timestamp when the workflow run reached a terminal status (COMPLETED, CANCELLED or FAILED)",
    )
    revision: int = Field(
        sa_column=Column(Integer, nullable=False, default=1),
        default=1,
        description="The project revision this workflow run belongs to",
    )
    heartbeat_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Written as each node starts and every few seconds while it runs; the reaper fails a RUNNING run whose heartbeat goes stale",
    )
    failure_reason: WorkflowRunFailureReason | None = Field(
        sa_column=Column(
            SQLModelEnum(WorkflowRunFailureReason),
            nullable=True,
        ),
        default=None,
        description="Populated only when status == FAILED",
    )
    failure_message: str | None = Field(
        sa_column=Column(String(2000), nullable=True),
        default=None,
        description="Short human-readable detail of the failure. Populated only when status == FAILED.",
    )
    model: str | None = Field(
        sa_column=Column(String(255), nullable=True),
        default=None,
        description=(
            "The model this run was asked to run every agent on, when the start "
            "request named one. Null means each agent's own model. Kept on the run "
            "so a run released later from a gate still runs on it."
        ),
    )
    # The next three are the job queue's alone: excluded from every response
    # that serializes the row (the project list does).
    config_json: dict[str, Any] | None = Field(
        sa_column=Column(JSONB, nullable=True),
        default=None,
        exclude=True,
        description=(
            "The config the run was started with, without its API key: the job "
            "queue rebuilds the run's config from it when the run's turn comes. "
            "A start that joins a waiting run keeps the config already stored."
        ),
    )
    started_by_user_id: uuid.UUID | None = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        default=None,
        exclude=True,
        description=(
            "The user whose start created the run. The job runs it as them (their "
            "stored API key, their trace user id)."
        ),
    )
    encrypted_openai_api_key: str | None = Field(
        sa_column=Column(String, nullable=True),
        default=None,
        exclude=True,
        description=(
            "The API key the start request named, encrypted like a user's stored "
            "key. The job takes it when it claims the run, which clears it; a run "
            "that ends unclaimed clears it too."
        ),
    )
    independent_run: bool = Field(
        sa_column=Column(
            Boolean, nullable=False, default=False, server_default=text("false")
        ),
        default=False,
        description=(
            "Copied from the manifest's independent_runs when the run is created. "
            "Such runs go side by side, so the one-running and one-waiting "
            "indexes leave them out."
        ),
    )
    state_json: dict[str, Any] | None = Field(
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


class WorkflowRunPublic(BaseModel):
    """A workflow run as exposed in project responses: every column of
    ``WorkflowRun`` except ``state_json`` and the columns only the job queue
    reads (``config_json``, ``started_by_user_id``, ``encrypted_openai_api_key``).

    Responses that embed a run also carry its hydrated ``state``, so the raw
    JSON would only duplicate it (1.5 MB each on a fully analysed project).
    Built from the ORM row by attribute access; the raw JSON stays available
    through the dedicated raw-state endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    # Field optionality mirrors WorkflowRun so the generated frontend type is a
    # drop-in for the one it replaces: nullable timestamps are always present,
    # only revision and the failure fields are optional.
    id: uuid.UUID
    project_id: uuid.UUID | None
    type: WorkflowRunType
    langgraph_thread_id: str
    status: WorkflowRunStatus
    created_at: datetime
    last_updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    revision: int = 1
    heartbeat_at: datetime | None
    failure_reason: WorkflowRunFailureReason | None = None
    failure_message: str | None = None
    model: str | None = None


# Mark `state_json` as deferred-load by default. Payloads can be multiple MB
# (p99 ≈ 3 MB, max 13 MB observed); hauling them through every SELECT on
# workflow_runs would be a major regression in the reaper, status checks,
# cancel paths, and list endpoints. Callers that actually need state should
# opt in with `select(...).options(undefer(col(WorkflowRun.state_json)))` or,
# inside the session, `await session.refresh(run, ["state_json"])`. Touching
# the attribute on a row loaded without it does not lazy-load: the async engine
# rejects the implicit IO, and a row whose session has closed cannot load at all.
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
