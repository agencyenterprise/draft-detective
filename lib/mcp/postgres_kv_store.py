"""Postgres-backed AsyncKeyValue store for FastMCP OAuth state.

Plugs into FastMCP OAuth providers via ``client_storage=``. Every acquire is
one short transaction; no background tasks, no locks. Concurrent writes to
the same ``(collection, key)`` are serialised by the composite primary key
via ``ON CONFLICT DO UPDATE``.

Rows can carry an ``expires_at``; expired rows are filtered out of reads and
deleted lazily so stale state doesn't accumulate forever. No background
sweeper — volume from OAuth flows is tiny.
"""

import logging
from collections.abc import Sequence
from datetime import datetime

from key_value.aio._utils.managed_entry import ManagedEntry
from key_value.aio.stores.base import BaseStore
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col

from lib.config.database import AsyncSessionLocal
from lib.models.mcp_oauth_kv import MCPOAuthKV

logger = logging.getLogger(__name__)


def _to_managed_entry(row: MCPOAuthKV) -> ManagedEntry:
    return ManagedEntry(
        value=row.value,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


class PostgresKeyValueStore(BaseStore):
    """Shared-across-pods AsyncKeyValue store backed by the ``mcp_oauth_kv`` table.

    FastMCP's ``BaseStore`` handles the protocol boilerplate (TTL evaluation,
    batch iteration when only a single-entry hook is defined, collection
    sanitisation). We only implement the three required managed-entry hooks
    plus batch overrides that collapse N operations into one SQL statement.
    """

    def __init__(self) -> None:
        # stable_api=True suppresses the "unstable store" warning; our DB
        # schema is under our own migration control.
        super().__init__(stable_api=True)

    async def _get_managed_entry(self, *, collection: str, key: str) -> ManagedEntry | None:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(MCPOAuthKV).where(
                        col(MCPOAuthKV.collection) == collection,
                        col(MCPOAuthKV.key) == key,
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                return None

            entry = _to_managed_entry(row)
            if entry.is_expired:
                await session.execute(
                    delete(MCPOAuthKV).where(
                        col(MCPOAuthKV.collection) == collection,
                        col(MCPOAuthKV.key) == key,
                    )
                )
                await session.commit()
                return None

            return entry

    async def _get_managed_entries(
        self, *, collection: str, keys: Sequence[str]
    ) -> list[ManagedEntry | None]:
        if not keys:
            return []

        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(MCPOAuthKV).where(
                        col(MCPOAuthKV.collection) == collection,
                        col(MCPOAuthKV.key).in_(list(keys)),
                    )
                )
            ).scalars().all()

            by_key = {row.key: row for row in rows}
            expired_keys: list[str] = []
            results: list[ManagedEntry | None] = []
            for key in keys:
                row = by_key.get(key)
                if row is None:
                    results.append(None)
                    continue
                entry = _to_managed_entry(row)
                if entry.is_expired:
                    expired_keys.append(key)
                    results.append(None)
                else:
                    results.append(entry)

            if expired_keys:
                await session.execute(
                    delete(MCPOAuthKV).where(
                        col(MCPOAuthKV.collection) == collection,
                        col(MCPOAuthKV.key).in_(expired_keys),
                    )
                )
                await session.commit()

            return results

    async def _put_managed_entry(
        self,
        *,
        collection: str,
        key: str,
        managed_entry: ManagedEntry,
    ) -> None:
        created_at = managed_entry.created_at or datetime.now().astimezone()
        async with AsyncSessionLocal() as session:
            stmt = pg_insert(MCPOAuthKV).values(
                collection=collection,
                key=key,
                value=dict(managed_entry.value),
                created_at=created_at,
                expires_at=managed_entry.expires_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["collection", "key"],
                set_={
                    "value": stmt.excluded.value,
                    "created_at": stmt.excluded.created_at,
                    "expires_at": stmt.excluded.expires_at,
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def _put_managed_entries(
        self,
        *,
        collection: str,
        keys: Sequence[str],
        managed_entries: Sequence[ManagedEntry],
        ttl: float | None,  # unused — expires_at already baked into entries
        created_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        if not keys:
            return

        async with AsyncSessionLocal() as session:
            rows = [
                {
                    "collection": collection,
                    "key": key,
                    "value": dict(entry.value),
                    "created_at": entry.created_at or created_at,
                    "expires_at": entry.expires_at or expires_at,
                }
                for key, entry in zip(keys, managed_entries, strict=True)
            ]
            stmt = pg_insert(MCPOAuthKV).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["collection", "key"],
                set_={
                    "value": stmt.excluded.value,
                    "created_at": stmt.excluded.created_at,
                    "expires_at": stmt.excluded.expires_at,
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def _delete_managed_entry(self, *, key: str, collection: str) -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(MCPOAuthKV).where(
                    col(MCPOAuthKV.collection) == collection,
                    col(MCPOAuthKV.key) == key,
                )
            )
            await session.commit()
            return (result.rowcount or 0) > 0

    async def _delete_managed_entries(
        self, *, keys: Sequence[str], collection: str
    ) -> int:
        if not keys:
            return 0
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(MCPOAuthKV).where(
                    col(MCPOAuthKV.collection) == collection,
                    col(MCPOAuthKV.key).in_(list(keys)),
                )
            )
            await session.commit()
            return result.rowcount or 0

    async def cull(self) -> None:
        """Delete all rows whose ``expires_at`` has passed. Safe to call periodically."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(MCPOAuthKV).where(
                    col(MCPOAuthKV.expires_at).is_not(None),
                    col(MCPOAuthKV.expires_at) <= func.now(),
                )
            )
            await session.commit()
