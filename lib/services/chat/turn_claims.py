"""Which turn holds a chat thread, kept where every API worker can see it.

The API runs several workers, and a turn runs detached from the request that started
it (``detached_turn``). A reload or a second tab can land on a worker that doesn't
hold the turn, so the turn's state is on the ``chat_threads`` row:

- ``turn_started_at`` is the claim, and its token. A second turn on the thread is
  refused while it's held, as the Word add-in does (``word/chat_threads.claim``).
- ``turn_seen_at`` is stamped by the running turn every few seconds. A claim not
  stamped within ``STALE_TURN`` belongs to a turn that died with its worker, and the
  next turn may take it.
- ``cancel_requested_at`` is how any worker asks the running turn to stop; the turn
  sees it on its next stamp.

None of these writes move the thread in the list: ``last_updated_at`` is kept as is.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.chat_thread import STALE_TURN, ChatThread

# Without it the column's ``onupdate`` would stamp every claim write as activity.
_KEEP_UPDATED_AT = {"last_updated_at": col(ChatThread.last_updated_at)}


async def claim(thread_id: uuid.UUID) -> datetime | None:
    """Take the thread for one turn: the claim's token, or None while another holds it."""

    now = datetime.now(UTC)
    async with get_async_db_session() as session:
        claimed = await session.execute(
            update(ChatThread)
            .where(col(ChatThread.id) == thread_id)
            .where(
                or_(
                    col(ChatThread.turn_started_at).is_(None),
                    col(ChatThread.turn_seen_at).is_(None),
                    col(ChatThread.turn_seen_at) < now - STALE_TURN,
                )
            )
            .values(
                turn_started_at=now,
                turn_seen_at=now,
                cancel_requested_at=None,
                **_KEEP_UPDATED_AT,
            )
            .returning(col(ChatThread.turn_started_at))
        )
        token = claimed.scalar_one_or_none()
        await session.commit()
    return token


async def keep(thread_id: uuid.UUID, token: datetime) -> bool:
    """Stamp the turn as alive. False when it should stop: asked to, or its claim is gone."""

    async with get_async_db_session() as session:
        kept = await session.execute(
            update(ChatThread)
            .where(col(ChatThread.id) == thread_id)
            .where(col(ChatThread.turn_started_at) == token)
            .values(turn_seen_at=datetime.now(UTC), **_KEEP_UPDATED_AT)
            .returning(col(ChatThread.cancel_requested_at))
        )
        row = kept.one_or_none()
        await session.commit()
    return row is not None and row[0] is None


async def release(thread_id: uuid.UUID, token: datetime) -> None:
    """Let the next turn run, if this turn still holds the claim.

    A turn whose claim went stale and was taken must not let go of the one that
    replaced it.
    """

    async with get_async_db_session() as session:
        await session.execute(
            update(ChatThread)
            .where(col(ChatThread.id) == thread_id)
            .where(col(ChatThread.turn_started_at) == token)
            .values(
                turn_started_at=None,
                turn_seen_at=None,
                cancel_requested_at=None,
                **_KEEP_UPDATED_AT,
            )
        )
        await session.commit()


async def request_cancel(thread_id: uuid.UUID) -> bool:
    """Ask the thread's running turn to stop. False when no turn is running."""

    async with get_async_db_session() as session:
        asked = await session.execute(
            update(ChatThread)
            .where(col(ChatThread.id) == thread_id)
            .where(col(ChatThread.turn_started_at).is_not(None))
            .values(cancel_requested_at=datetime.now(UTC), **_KEEP_UPDATED_AT)
            .returning(col(ChatThread.id))
        )
        found = asked.scalar_one_or_none() is not None
        await session.commit()
    return found
