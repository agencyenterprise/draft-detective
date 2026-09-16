"""Proposed-edit rows attached to a persisted issue.

An `IssueEdit` is one mechanical text replacement an agent proposed alongside
an issue: replace `original_text` (located at `start_line`..`end_line` of the
main document markdown) with `replacement_text`.

Rows share the lifecycle of the issue that owns them. They are written with
their issue, they are archived with it (the status flip lives on `Issue`, and
edits are only ever read through their parent), and they are deleted with it --
the foreign key cascades on delete and the ORM relationship is
`delete-orphan`. Nothing rewrites or reorders them after the fact; `position`
preserves the order the agent proposed them in.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Enum as SQLModelEnum
from sqlmodel import Field, SQLModel


class IssueEditStatus(str, Enum):
    """Review state of a single proposed edit."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class IssueEdit(SQLModel, table=True):
    """One proposed text replacement belonging to an issue."""

    __tablename__ = "issue_edits"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="Unique identifier for the proposed edit",
    )

    issue_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("issues.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="The issue this edit resolves",
    )

    position: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="0-based order of this edit within its issue",
    )

    original_text: str = Field(
        sa_column=Column(Text, nullable=False),
        description=(
            "The exact text quoted from the main document markdown that this "
            "edit replaces. Never empty."
        ),
    )

    replacement_text: str = Field(
        sa_column=Column(Text, nullable=False),
        description=(
            "The text that takes the place of original_text. An empty string "
            "deletes the quoted span."
        ),
    )

    start_line: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="1-indexed first line of the main document markdown containing original_text",
    )

    end_line: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="1-indexed last line of the main document markdown containing original_text",
    )

    rationale: str = Field(
        sa_column=Column(Text, nullable=False),
        description="One short sentence explaining why this replacement resolves the issue",
    )

    status: IssueEditStatus = Field(
        sa_column=Column(
            SQLModelEnum(IssueEditStatus),
            nullable=False,
            default=IssueEditStatus.PROPOSED,
        ),
        default=IssueEditStatus.PROPOSED,
        description="Whether the edit is still proposed, or was accepted or rejected",
    )

    reviewed_by: Optional[uuid.UUID] = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        default=None,
        description="User who accepted or rejected this edit (null while proposed)",
    )

    reviewed_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
        description="When the edit was accepted or rejected",
    )

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="When the edit was created",
    )

    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        ),
        description="When the edit was last updated",
    )

    def __repr__(self):
        return (
            f"<IssueEdit(id={self.id}, issue_id={self.issue_id}, "
            f"position={self.position}, status={self.status.value})>"
        )


class IssueEditRead(BaseModel):
    """Read-only view of an `IssueEdit`, as published by every issue payload."""

    id: uuid.UUID
    issue_id: uuid.UUID
    original_text: str
    replacement_text: str
    start_line: int
    end_line: int
    rationale: str
    status: IssueEditStatus
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
