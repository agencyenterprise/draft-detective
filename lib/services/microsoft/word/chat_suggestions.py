"""Suggestions made in the add-in's chat: handoffs that belong to a chat thread.

The chat agent stores its comments and tracked changes as handoffs
(``lib/services/microsoft/word/handoffs.py``), so they are claimed, applied and
reported exactly like the ones from Teams. Three things are particular to the chat:

- **The card reads one by id**, whatever its status, so a suggestion already applied or
  dismissed still shows what became of it when the conversation is reloaded.
- **One card per answer.** The agent may store its suggestions in several calls (it
  batches long lists), and each call after the first adds to the answer's card
  (``replace_items``) rather than opening another.
- **The agent hears what became of them.** Applying happens in the pane, between turns,
  so the next message carries a note saying what was applied, what was not and why, or
  that they were dismissed. Without it the agent would offer the same changes again, or
  talk as if ones that never landed were in the document.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.services.microsoft.word.handoffs import (
    OPEN,
    Account,
    FinishedHandoff,
    HandoffItems,
    HandoffOutcome,
    fresh,
    owned_by,
    report,
)

SuggestionStatus = Literal["pending", "applying", "applied", "dismissed"]


class ChatSuggestion(BaseModel):
    """One set of suggestions from the chat, as its card shows it."""

    id: uuid.UUID
    chat_thread_id: uuid.UUID | None = None
    status: SuggestionStatus
    document_name: str
    document_url: str
    items: HandoffItems
    outcome: HandoffOutcome | None = None
    created_at: datetime
    finished_at: datetime | None = None
    heard_at: datetime | None = None


def _view(row: MicrosoftWordHandoff) -> ChatSuggestion:
    return ChatSuggestion(
        id=row.id,
        chat_thread_id=row.chat_thread_id,
        status=row.status,  # type: ignore[arg-type]  # the column holds only these four
        document_name=row.document_name,
        document_url=row.document_url,
        items=HandoffItems.model_validate(row.items),
        outcome=HandoffOutcome.model_validate(row.outcome) if row.outcome else None,
        created_at=row.created_at,
        finished_at=row.finished_at,
        heard_at=row.heard_at,
    )


async def suggestion_for(
    handoff_id: uuid.UUID, account: Account
) -> ChatSuggestion | None:
    """One of this account's chat suggestions, in any status. None once it expired."""

    async with get_async_db_session() as session:
        row = (
            await session.execute(
                select(MicrosoftWordHandoff)
                .where(col(MicrosoftWordHandoff.id) == handoff_id)
                .where(col(MicrosoftWordHandoff.chat_thread_id).is_not(None))
                .where(owned_by(account))
                .where(fresh())
            )
        ).scalar_one_or_none()
    return _view(row) if row is not None else None


async def for_thread(chat_thread_id: uuid.UUID) -> list[ChatSuggestion]:
    """Every live suggestion a chat thread made, oldest first."""

    async with get_async_db_session() as session:
        rows = await session.execute(
            select(MicrosoftWordHandoff)
            .where(col(MicrosoftWordHandoff.chat_thread_id) == chat_thread_id)
            .where(fresh())
            .order_by(col(MicrosoftWordHandoff.created_at))
        )
        return [_view(row) for row in rows.scalars().all()]


async def replace_items(
    handoff_id: uuid.UUID, account: Account, items: HandoffItems
) -> bool:
    """Set the items of one of this account's chat cards, while it is still pending.

    One conditional UPDATE: a card being applied, applied, dismissed or expired is never
    changed, and False says so, so the caller opens a new card instead.
    """

    async with get_async_db_session() as session:
        row = (
            await session.execute(
                update(MicrosoftWordHandoff)
                .where(col(MicrosoftWordHandoff.id) == handoff_id)
                .where(col(MicrosoftWordHandoff.chat_thread_id).is_not(None))
                .where(owned_by(account))
                .where(col(MicrosoftWordHandoff.status) == "pending")
                .where(fresh())
                .values(items=items.model_dump(mode="json"))
                .returning(col(MicrosoftWordHandoff.id))
            )
        ).first()
        await session.commit()
    return row is not None


def news(suggestions: list[ChatSuggestion]) -> str:
    """What the agent should hear about its suggestions at the start of a turn.

    Each one that settled and that it has not been told about is described once, worded
    from what was stored, never from client text: a card it waited on was told by
    ``ask_to_apply``, so only the others are news. Ones still waiting are mentioned so
    they are not offered again. Empty when there is nothing to say.
    """

    lines = [settled_summary(suggestion) for suggestion in unheard(suggestions)]
    waiting = sum(1 for suggestion in suggestions if suggestion.status in OPEN)
    if waiting:
        lines.append(
            f"{waiting} set(s) of your earlier suggestions are still waiting for them "
            "to apply or dismiss."
        )
    if not lines:
        return ""
    return "[About your earlier suggestions:\n" + "\n".join(lines) + "]"


def unheard(suggestions: list[ChatSuggestion]) -> list[ChatSuggestion]:
    """The settled ones the agent has not been told about."""

    return [s for s in suggestions if s.finished_at is not None and s.heard_at is None]


async def mark_heard(ids: list[uuid.UUID]) -> None:
    """Record that the agent has been told how these ended, so it is told once."""

    if not ids:
        return
    async with get_async_db_session() as session:
        await session.execute(
            update(MicrosoftWordHandoff)
            .where(col(MicrosoftWordHandoff.id).in_(ids))
            .where(col(MicrosoftWordHandoff.heard_at).is_(None))
            .values(heard_at=datetime.now(UTC))
        )
        await session.commit()


def settled_summary(suggestion: ChatSuggestion) -> str:
    if suggestion.status == "dismissed":
        count = suggestion.items.count
        return f"They dismissed a set of {count} suggestion(s); none were applied."
    outcome = suggestion.outcome or HandoffOutcome()
    finished = FinishedHandoff(
        document_name=suggestion.document_name, items=suggestion.items
    )
    return report(finished, outcome)
