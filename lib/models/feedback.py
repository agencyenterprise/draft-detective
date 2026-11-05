"""Feedback system models: a user's thumbs up or down on an issue."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Enum as SQLModelEnum
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, String


class FeedbackType(str, Enum):
    """Type of feedback provided by users"""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class Feedback(SQLModel, table=True):
    """A user's rating of one issue.

    `workflow_run_id` is copied from the issue when the feedback is saved, so
    ownership checks and the admin queries can reach the run without going
    through the issue.
    """

    __tablename__ = "feedback"
    __table_args__ = (
        Index(
            "ix_feedback_feedback_text_trgm",
            "feedback_text",
            postgresql_using="gin",
            postgresql_ops={"feedback_text": "gin_trgm_ops"},
        ),
    )

    id: uuid.UUID = SQLField(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )

    workflow_run_id: uuid.UUID = SQLField(
        sa_column=Column(UUID(as_uuid=True), nullable=False, index=True),
        description="The workflow run this feedback belongs to",
    )

    user_id: uuid.UUID = SQLField(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="The user who created this feedback",
    )

    issue_id: uuid.UUID = SQLField(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("issues.id", ondelete="CASCADE", use_alter=True),
            nullable=False,
            index=True,
        ),
        description="The issue this feedback is about",
    )

    feedback_type: FeedbackType = SQLField(
        sa_column=Column(SQLModelEnum(FeedbackType), nullable=False),
        description="Type of feedback (thumbs up/down)",
    )

    feedback_text: str | None = SQLField(
        sa_column=Column(String, nullable=True),
        default=None,
        description="Optional feedback text",
    )

    created_at: datetime = SQLField(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        )
    )

    updated_at: datetime = SQLField(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )
    )

    def __repr__(self):
        return f"<Feedback(workflow_run_id={self.workflow_run_id}, issue_id={self.issue_id}, type={self.feedback_type})>"
