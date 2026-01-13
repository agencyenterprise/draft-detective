"""Workflow progress tracking models."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class ProgressLevel(str, Enum):
    """Level of progress tracking."""

    WORKFLOW = "workflow"
    NODE = "node"
    TASK = "task"


class WorkflowProgress(SQLModel, table=True):
    """Progress tracking for workflows, nodes, and tasks."""

    __tablename__ = "workflow_progress"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="Unique identifier for the progress entry",
    )
    workflow_run_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="FK to the workflow run this progress belongs to",
    )
    name: str = Field(
        max_length=255,
        description="Human-readable name of what's being tracked",
    )
    level: ProgressLevel = Field(
        description="Level of progress: workflow, node, or task"
    )
    current_step: int = Field(
        default=0, description="Current step/item being processed"
    )
    total_steps: int = Field(default=0, description="Total steps/items to process")
    started_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
        description="When this progress entry started",
    )
    completed_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
        description="When this progress entry completed",
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="When this progress entry was created",
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        ),
        description="When this progress entry was last updated",
    )

    @property
    def status(self) -> str:
        """Derive status from timestamps."""
        if self.completed_at:
            return "completed"
        if self.started_at:
            return "in_progress"
        return "pending"

    def __repr__(self):
        return f"<WorkflowProgress(id={self.id}, name={self.name}, level={self.level}, status={self.status})>"
