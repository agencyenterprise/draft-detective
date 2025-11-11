from enum import Enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel, String, Enum as SQLModelEnum


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    langgraph_thread_id: str = Field(sa_column=Column(String(255), nullable=False))
    title: str = Field(sa_column=Column(String, nullable=False))
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        )
    )
    last_updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )
    )
    status: WorkflowRunStatus = Field(
        sa_column=Column(
            SQLModelEnum(WorkflowRunStatus),
            nullable=False,
            default=WorkflowRunStatus.PENDING,
        )
    )

    def __repr__(self):
        return f"<WorkflowRun(id={self.id}, langgraph_thread_id={self.langgraph_thread_id})>"
