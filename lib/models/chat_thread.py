import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

# A running turn stamps ``turn_seen_at`` every few seconds (``turn_claims.keep``). A
# claim not stamped for this long is a turn that died without releasing it: a worker
# restart. Long turns stay claimed for as long as they run.
STALE_TURN = timedelta(minutes=2)


class ChatThread(SQLModel, table=True):
    """A chat thread belonging to a user: the index entry, not the conversation.

    What was said lives in the LangGraph checkpointer, keyed by this row's id
    (see ``lib/services/chat/history.py``). This table holds what the
    checkpointer cannot: who owns the thread, its title, and whether it is
    archived, and whether a turn is running on it now (see
    ``lib/services/chat/turn_claims.py``). Its id is its row's in ``conversations``
    (``lib/models/conversation.py``); deleting the thread deletes that row, and
    this one with it.
    """

    __tablename__ = "chat_threads"
    __table_args__ = (Index("ix_chat_threads_user_id", "user_id"),)

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
            default=uuid.uuid4,
        ),
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
    title: str | None = Field(
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
    turn_started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description=(
            "When the turn running now began, if one is; also the claim's token "
            "(``turn_claims.claim``)"
        ),
    )
    turn_seen_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the running turn last showed it was alive",
    )
    cancel_requested_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When someone asked the running turn to stop",
    )

    @property
    def is_running(self) -> bool:
        """Whether a turn holds the thread now: claimed, and not gone stale."""

        if self.turn_started_at is None or self.turn_seen_at is None:
            return False
        return self.turn_seen_at > datetime.now(UTC) - STALE_TURN
