from typing import Optional
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Enum as SQLModelEnum
from sqlmodel import Field, SQLModel, String

from lib.workflows.models import WorkflowRunType


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"


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
        default=None,
        description="The timestamp when the workflow started running",
    )
    completed_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
        description="The timestamp when the workflow completed",
    )

    def __repr__(self):
        return f"<WorkflowRun(id={self.id}, langgraph_thread_id={self.langgraph_thread_id})>"
