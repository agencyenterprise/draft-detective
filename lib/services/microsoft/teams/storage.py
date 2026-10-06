"""Questions waiting for their askers to sign in, shared across workers.

When someone without a token asks the bot something, the question is parked here and
they are shown a sign-in card (``sign_in.py``). It is taken back out by the card action
that follows the sign-in -- a *different request*, which in production usually lands on
a *different process*, since Uvicorn is launched with ``--workers 4``. Process memory
cannot span that, so first-time sign-in would fail about three times in four, and only
once deployed: a single-process dev server never shows it.

It is also the Agents SDK's ``Storage``, which the bot's application requires. The SDK
reads its turn state from it on every turn, but the bot keeps none, so nothing of the
SDK's is written.

One short transaction per operation, no locks. Concurrent writes to the same key are
serialised by the primary key via ``ON CONFLICT DO UPDATE``.

**Rows are swept, because a sign-in nobody finishes never deletes its own.** A question
is removed when it is answered, so the rows that linger are the ones where somebody saw
the Sign in card and walked away -- and what is stored is the question itself, meaning
its text and its sender. Left alone, that is confidential content retained indefinitely
in a table whose rows otherwise live for a minute or two. Every write therefore drops
rows older than ``ABANDONED_AFTER``, which costs an indexed range delete and needs no
scheduler.

No tokens pass through here. The refresh token stays in the Bot Framework token
service; what is stored is the question waiting to be answered, and where to answer it.
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

# Generous next to the thing being measured: a sign-in takes about a minute, so a row
# untouched for an hour belongs to a sign-in that was abandoned rather than one still in
# progress. Long enough that a slow sign-in is never swept out from under
# someone, short enough that a parked message is not kept for days.
ABANDONED_AFTER = timedelta(hours=1)


class PostgresSignInStorage(AsyncStorageBase):
    """Parked questions in Postgres rather than in one worker's memory.

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
        parked question has to be exclusive -- the button can be pressed twice, and Teams
        retries an invoke it did not hear back from -- or the question is answered twice.
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
    """The storage the bot's application is built with.

    A function rather than a module-level instance so importing this module does not
    imply a database connection, which matters for tests and for a deployment that
    does not run the bot.
    """

    return PostgresSignInStorage()
