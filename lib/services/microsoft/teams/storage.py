"""The Agents SDK's storage, shared across workers.

The SDK keeps an in-progress sign-in here: the flow's state, and the question parked
to be replayed once a token arrives. Both are written by the request that posts the
Sign in card and read by the later ``signin/*`` invoke -- a *different request*, which
in production usually lands on a *different process*, since Uvicorn is launched with
``--workers 4``. The SDK's own ``MemoryStorage`` cannot span that, so first-time
sign-in would fail about three times in four, and only once deployed: a single-process
dev server never shows it.

One short transaction per operation, no locks. Concurrent writes to the same key are
serialised by the primary key via ``ON CONFLICT DO UPDATE``.

**Rows are swept, because a sign-in nobody finishes never deletes its own.** The SDK
removes an entry when a flow completes or fails, so the rows that linger are the ones
where somebody saw the Sign in card and closed it -- and one of the two things stored is
the message that was parked to be replayed, meaning its text and its sender. Left alone,
that is confidential content retained indefinitely in a table whose lifetime is
otherwise measured in seconds. Every write therefore drops rows older than
``ABANDONED_AFTER``, which costs an indexed range delete and needs no scheduler.

No tokens pass through here. The refresh token stays in the Bot Framework token
service; what is stored is flow bookkeeping and the pending activity.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from microsoft_agents.hosting.core import Storage
from microsoft_agents.hosting.core.storage import AsyncStorageBase, StoreItem
from sqlalchemy import CursorResult, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.microsoft_teams_signin_state import MicrosoftTeamsSignInState

logger = logging.getLogger(__name__)

# Generous next to the thing being measured: the SDK's own flow lasts about a minute,
# so a row untouched for an hour belongs to a sign-in that was abandoned rather than one
# still in progress. Long enough that a slow sign-in is never swept out from under
# someone, short enough that a parked message is not kept for days.
ABANDONED_AFTER = timedelta(hours=1)


class PostgresSignInStorage(AsyncStorageBase):
    """Sign-in state in Postgres rather than in one worker's memory.

    ``AsyncStorageBase`` implements the bulk ``read``/``write``/``delete`` in terms of
    the three single-item hooks below, so only those are needed.
    """

    async def _read_item(
        self, key: str, *, target_cls: type[Any], **kwargs: Any
    ) -> tuple[str | None, Any | None]:
        async with get_async_db_session() as session:
            row = (
                await session.execute(
                    select(MicrosoftTeamsSignInState).where(
                        col(MicrosoftTeamsSignInState.key) == key
                    )
                )
            ).scalar_one_or_none()

        if row is None:
            return None, None
        return key, target_cls.from_json_to_store_item(row.value)

    async def _write_item(self, key: str, value: StoreItem) -> None:
        payload = value.store_item_to_json()
        now = datetime.now(timezone.utc)
        statement = (
            pg_insert(MicrosoftTeamsSignInState)
            .values(key=key, value=payload, updated_at=now)
            # A retried turn rewrites the same key rather than colliding with itself.
            .on_conflict_do_update(
                index_elements=[MicrosoftTeamsSignInState.key],
                set_={"value": payload, "updated_at": now},
            )
        )
        async with get_async_db_session() as session:
            await session.execute(statement)
            # Same transaction as the write, so a sweep cannot be the thing that fails
            # on its own and leaves the caller thinking nothing happened.
            # A DELETE really does come back as a CursorResult, which carries
            # rowcount; the stubs only promise the narrower Result.
            swept = cast(
                CursorResult[Any],
                await session.execute(
                    delete(MicrosoftTeamsSignInState).where(
                        col(MicrosoftTeamsSignInState.updated_at)
                        < now - ABANDONED_AFTER
                    )
                ),
            )
            await session.commit()

        if swept.rowcount:
            logger.info(
                "swept %s abandoned Teams sign-in row(s)", swept.rowcount
            )

    async def _delete_item(self, key: str) -> None:
        async with get_async_db_session() as session:
            await session.execute(
                delete(MicrosoftTeamsSignInState).where(
                    col(MicrosoftTeamsSignInState.key) == key
                )
            )
            await session.commit()

    async def take(self, key: str) -> dict[str, Any] | None:
        """Remove an item and return what it held, in one statement.

        A read followed by a delete would let two requests both see the item. Taking a
        parked question has to be exclusive -- Teams can send the same card action
        twice, once on its own and once because someone clicked -- or the question is
        answered twice.
        """

        async with get_async_db_session() as session:
            value = (
                await session.execute(
                    delete(MicrosoftTeamsSignInState)
                    .where(col(MicrosoftTeamsSignInState.key) == key)
                    .returning(col(MicrosoftTeamsSignInState.value))
                )
            ).scalar_one_or_none()
            await session.commit()
        return value


def sign_in_storage() -> Storage:
    """The storage the bot's ``Authorization`` should use.

    A function rather than a module-level instance so importing this module does not
    imply a database connection, which matters for tests and for a deployment that
    does not run the bot.
    """

    return PostgresSignInStorage()
