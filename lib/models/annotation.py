"""
Human annotation models.

Users label small, self-contained items drawn from the eval datasets ("should
this sentence be flagged?"), so the synthetic ground truth and the LLM judges
can be checked against people. One shape serves every eval:

- An ``AnnotationSet`` is one eval (Active Voice, Advocacy & Tone, ...). It
  carries the guidance annotators read and the questions they answer.
- An ``AnnotationItem`` is one thing to judge. Its ``payload`` is whatever the
  UI needs to show it (a document and the passage in question) and its
  ``reference_answers`` are the eval's own answers, keyed like the questions,
  so agreement is computed the same way for every set.
- An ``Annotation`` is one user's answers to one item.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Enum as SQLModelEnum
from sqlmodel import Field, SQLModel


class AnnotationItemKind(str, Enum):
    """Where an item comes from in the eval dataset."""

    EXPECTED_ISSUE = "expected_issue"
    DECOY = "decoy"


class AnnotationItemStatus(str, Enum):
    """Retired items left the dataset; their annotations are kept."""

    ACTIVE = "active"
    RETIRED = "retired"


def _timestamp_column(onupdate: bool = False) -> Column:
    return Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow if onupdate else None,
        nullable=False,
    )


class AnnotationSet(SQLModel, table=True):
    """One eval's annotation task: guidance, questions and its items."""

    __tablename__ = "annotation_sets"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    slug: str = Field(
        sa_column=Column(String, nullable=False, unique=True),
        description="Stable identifier, the eval directory name (e.g. active_voice)",
    )
    title: str = Field(sa_column=Column(String, nullable=False))
    workflow_type: str = Field(
        sa_column=Column(String, nullable=False),
        description="The workflow the eval exercises",
    )
    summary: str = Field(
        sa_column=Column(Text, nullable=False),
        description="One sentence shown on the set's card",
    )
    guidance: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Markdown shown to annotators: what the check flags and what it leaves alone",
    )
    questions: list[dict] = Field(
        sa_column=Column(JSONB, nullable=False),
        description="The questions each item asks, as AnnotationQuestion dicts",
    )
    is_active: bool = Field(sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime = Field(sa_column=_timestamp_column())
    updated_at: datetime = Field(sa_column=_timestamp_column(onupdate=True))


class AnnotationItem(SQLModel, table=True):
    """One item to judge. The eval's own answers are for admins only, never shown to annotators."""

    __tablename__ = "annotation_items"
    __table_args__ = (
        UniqueConstraint("set_id", "source_key", name="uq_annotation_items_set_source"),
    )

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    set_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("annotation_sets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    source_key: str = Field(
        sa_column=Column(String, nullable=False),
        description="Identifies the item in its dataset; a changed document or passage is a new item",
    )
    kind: AnnotationItemKind = Field(
        sa_column=Column(SQLModelEnum(AnnotationItemKind), nullable=False)
    )
    status: AnnotationItemStatus = Field(
        sa_column=Column(
            SQLModelEnum(AnnotationItemStatus),
            nullable=False,
            default=AnnotationItemStatus.ACTIVE,
        )
    )
    payload: dict = Field(
        sa_column=Column(JSONB, nullable=False),
        description="What the UI shows, e.g. {document, anchor, line}",
    )
    reference_answers: dict = Field(
        sa_column=Column(JSONB, nullable=False),
        description="The eval dataset's answers, keyed by question",
    )
    reference_explanation: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Why the dataset answers that way, for the admin results view",
    )
    created_at: datetime = Field(sa_column=_timestamp_column())
    updated_at: datetime = Field(sa_column=_timestamp_column(onupdate=True))


class Annotation(SQLModel, table=True):
    """One user's answers to one item."""

    __tablename__ = "annotations"
    __table_args__ = (
        UniqueConstraint("item_id", "user_id", name="uq_annotations_item_user"),
    )

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    item_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("annotation_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    answers: dict = Field(
        sa_column=Column(JSONB, nullable=False),
        description="Answers keyed by question, e.g. {should_flag: 'yes'}",
    )
    comment: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    time_spent_ms: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="Time from the item being shown to the first answer",
    )
    created_at: datetime = Field(sa_column=_timestamp_column())
    updated_at: datetime = Field(sa_column=_timestamp_column(onupdate=True))
