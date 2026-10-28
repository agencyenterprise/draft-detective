"""A conversation with Draft Detective in the Word add-in's chat, about one document.

The conversation itself is in the LangGraph checkpointer, keyed by this row's id, as
for the /chat page (``lib/models/chat_thread.py``). This row says whose it is and which
document it is about, which the checkpointer cannot. Its id is its row's in
``conversations`` (``lib/models/conversation.py``).

It belongs to a Microsoft account, not to a Draft Detective user: the add-in signs in
as an Entra object id (``lib/api/addin_auth.py``), which may have no user row at all.
One account has one current thread per document. Clearing it sets ``cleared_at`` and the
next message starts a new one; the cleared thread stays here, unreachable from the pane.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


class MicrosoftWordChatThread(SQLModel, table=True):
    __tablename__ = "microsoft_word_chat_threads"
    __table_args__ = (Index("ix_microsoft_word_chat_threads_owner_oid", "owner_oid"),)

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
            default=uuid.uuid4,
        ),
        description="Also the LangGraph thread id the conversation is stored under",
    )
    owner_oid: str = Field(
        sa_column=Column(String, nullable=False),
        description="The Entra object id of the account that owns the thread",
    )
    owner_tid: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="That account's tenant, when its token named one",
    )
    document_name: str = Field(sa_column=Column(String, nullable=False))
    document_url: str = Field(
        sa_column=Column(String, nullable=False),
        description="The URL Word reported for the document when the thread began",
    )
    document_keys: list[str] = Field(
        sa_column=Column(JSONB, nullable=False),
        description=(
            "Every form under which Word may report the document's URL, as for "
            "handoffs (``handoffs.keys_for_url``)"
        ),
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_turn_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When the last message was sent; the newest thread is the current one",
    )
    running_since: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description=(
            "When the turn running now began, if one is: a second one waits for it "
            "(``chat_threads.claim``)"
        ),
    )
    cleared_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the person cleared the chat. A cleared thread is never resumed.",
    )
