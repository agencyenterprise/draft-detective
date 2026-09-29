"""Request and response models for human annotation."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from lib.models.annotation import AnnotationItemKind


class AnnotationOption(BaseModel):
    """One answer a question offers."""

    value: str = Field(description="Stored in answers and compared with the reference")
    label: str
    shortcut: Optional[str] = Field(
        default=None, description="Keyboard key that picks it"
    )


class AnnotationQuestion(BaseModel):
    """A question every item in a set asks."""

    key: str
    prompt: str
    options: list[AnnotationOption]
    abstain_value: Optional[str] = Field(
        default=None,
        description="The option meaning 'not sure'; it neither agrees nor disagrees with the reference",
    )


class AnnotationSetSummary(BaseModel):
    """A set as its card shows it, with the current user's progress."""

    slug: str
    title: str
    summary: str
    workflow_type: str
    item_count: int = Field(description="Active items in the set")
    answered_by_me: int = Field(
        description="Active items the current user has answered"
    )


class AnnotationPassage(BaseModel):
    """What the user judges: a passage in a short document."""

    document: str = Field(description="The document as markdown")
    anchor: str = Field(description="Verbatim passage to highlight")
    line: Optional[int] = Field(
        default=None, description="1-indexed line the passage is on"
    )


class AnnotationTaskSet(BaseModel):
    """The parts of a set the annotation screen needs."""

    slug: str
    title: str
    guidance: str
    questions: list[AnnotationQuestion]


class AnnotationTask(BaseModel):
    """The next item to judge. It never carries the reference answers."""

    set: AnnotationTaskSet
    item_id: Optional[uuid.UUID] = Field(
        default=None, description="None when the user has answered every item"
    )
    passage: Optional[AnnotationPassage] = None
    item_count: int
    answered_by_me: int


class AnnotationSubmission(BaseModel):
    """A user's answers to one item. Submitting again replaces them."""

    answers: dict[str, str]
    comment: Optional[str] = Field(default=None, max_length=4000)
    time_spent_ms: Optional[int] = Field(default=None, ge=0)


class AnnotationOutcome(BaseModel):
    """Confirms a saved answer. Deliberately says nothing about the reference
    answers: knowing how the dataset answered would sway the next answer."""

    item_id: uuid.UUID
    answered_by_me: int


class AnnotationSetStats(BaseModel):
    """Admin overview of one set."""

    slug: str
    title: str
    item_count: int
    annotated_items: int = Field(
        description="Active items with at least one annotation"
    )
    annotation_count: int
    annotator_count: int
    agreements: int = Field(description="Annotations that match the reference")
    disagreements: int = Field(description="Annotations that contradict the reference")
    abstentions: int


class AnnotationRecord(BaseModel):
    """One annotation as the admin view and the export show it."""

    user_name: str
    user_email: str
    answers: dict[str, str]
    agrees: Optional[bool]
    comment: Optional[str]
    time_spent_ms: Optional[int]
    created_at: datetime


class AnnotatedItem(BaseModel):
    """An item with every annotation it has received."""

    item_id: uuid.UUID
    source_key: str
    kind: AnnotationItemKind
    passage: AnnotationPassage
    reference_answers: dict[str, str]
    reference_explanation: Optional[str]
    annotations: list[AnnotationRecord]
    agreements: int
    disagreements: int
    abstentions: int
