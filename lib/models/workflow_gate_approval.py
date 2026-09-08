"""A user's approval of a workflow gate for one project revision."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel, String

from lib.workflows.models import WorkflowGate


class WorkflowGateApproval(SQLModel, table=True):
    """Records that a gate was approved for a project revision.

    One row per (project, revision, gate). Runs awaiting approval of that gate
    are released when the row is written, and later runs of gated
    workflows in the same revision start without asking again. A new revision
    has no rows, so the user reviews again against the new document.
    """

    __tablename__ = "workflow_gate_approvals"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "revision",
            "gate",
            name="uq_workflow_gate_approvals_project_revision_gate",
        ),
    )

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="Unique identifier for the approval",
    )
    project_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="The project the approval belongs to",
    )
    revision: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="The project revision the approval applies to",
    )
    gate: WorkflowGate = Field(
        sa_column=Column(String(64), nullable=False),
        description="The gate that was approved",
    )
    approved_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="When the gate was approved",
    )
    approved_by_user_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="The user who approved the gate, when known",
    )
