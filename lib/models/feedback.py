"""
Feedback system models.

This module provides a self-contained feedback system that uses coordinate-based
addressing to attach feedback to any entity.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, String, Enum as SQLModelEnum


class FeedbackType(str, Enum):
    """Type of feedback provided by users"""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class EntityPath(BaseModel):
    """Base class for entity coordinate paths"""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSONB storage"""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict) -> "EntityPath":
        """Create from dictionary"""
        return cls(**data)


class ClaimPath(EntityPath):
    """Coordinate path for claim-level feedback"""

    chunk_index: int = Field(ge=0, description="Zero-based chunk index")
    claim_index: int = Field(ge=0, description="Zero-based claim index within chunk")


class Feedback(SQLModel, table=True):
    """
    Independent feedback model using coordinate-based addressing.

    Feedback is stored separately from workflow state and uses stable coordinates
    (workflow_run_id + entity_path) to reference entities.
    """

    __tablename__ = "feedback"

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

    entity_path: dict = SQLField(
        sa_column=Column(JSONB, nullable=False),
        description="JSONB path identifying the entity (e.g., {chunk_index: 2, claim_index: 0})",
    )

    feedback_type: FeedbackType = SQLField(
        sa_column=Column(SQLModelEnum(FeedbackType), nullable=False),
        description="Type of feedback (thumbs up/down)",
    )

    feedback_text: Optional[str] = SQLField(
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
        return f"<Feedback(workflow_run_id={self.workflow_run_id}, entity_path={self.entity_path}, type={self.feedback_type})>"
