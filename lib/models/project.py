import uuid
from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Date, Index
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel, String


class FeedbackVisibility(str, Enum):
    PRIVATE = "private"
    ISSUE_ONLY = "issue_only"
    FULL_PROJECT = "full_project"


class AccessLevel(str, Enum):
    READ = "read"
    WRITE = "write"


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    __table_args__ = (
        Index(
            "ix_projects_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="The unique identifier for the project",
    )
    title: str = Field(
        sa_column=Column(String, nullable=False), description="The title of the project"
    )
    user_id: uuid.UUID = Field(
        default=None,
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="The user who created the project",
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="The timestamp when the project was created",
    )
    last_updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        ),
        description="The timestamp when the project was last updated",
    )
    publication_date: date = Field(
        sa_column=Column(Date, nullable=True),
        description="The publication date of the report",
    )
    domain: str = Field(
        sa_column=Column(String, nullable=True),
        description="The subject area or field of expertise of the report",
    )
    target_audience: str = Field(
        sa_column=Column(String, nullable=True),
        description="The intended readers of the report",
    )
    feedback_visibility: Optional[FeedbackVisibility] = Field(
        sa_column=Column(
            SQLAlchemyEnum(FeedbackVisibility, name="feedbackvisibility"),
            nullable=True,
        ),
        default=None,
        description="Controls what feedback information is shared with administrators",
    )
