import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class ChatThread(SQLModel, table=True):
    """A chat thread belonging to a user: the index entry, not the conversation.

    What was said lives in the LangGraph checkpointer, keyed by this row's id
    (see ``lib/services/chat/history.py``). This table holds what the
    checkpointer cannot: who owns the thread, its title, and whether it is
    archived.
    """

    __tablename__ = "chat_threads"
    __table_args__ = (Index("ix_chat_threads_user_id", "user_id"),)

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="The unique identifier for the chat thread",
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="Owner of the thread",
    )
    title: Optional[str] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="Human-readable thread title (generated from the conversation)",
    )
    is_archived: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Whether the thread is archived",
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
    )
    last_updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        ),
    )
