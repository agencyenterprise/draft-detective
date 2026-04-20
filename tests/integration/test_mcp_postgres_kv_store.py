"""Integration tests for PostgresKeyValueStore.

Hits the real Postgres used by the rest of the test suite (same DATABASE_URL).
Verifies the FastMCP AsyncKeyValue contract: round-trip, TTL expiry + lazy
cleanup, batch ops, collection isolation, and upsert-overwrites semantics.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.mcp.postgres_kv_store import PostgresKeyValueStore
from lib.models.mcp_oauth_kv import MCPOAuthKV


@pytest_asyncio.fixture
async def collection():
    """Unique collection per test so parallel runs don't interfere."""
    name = f"test-{uuid.uuid4().hex[:12]}"
    yield name

    async with get_async_db_session() as session:
        await session.execute(
            delete(MCPOAuthKV).where(col(MCPOAuthKV.collection) == name)
        )
        await session.commit()


@pytest_asyncio.fixture
async def store():
    return PostgresKeyValueStore()


@pytest.mark.asyncio
async def test_round_trip(store, collection):
    await store.put("k1", {"client_id": "abc", "scopes": ["a", "b"]}, collection=collection)
    got = await store.get("k1", collection=collection)
    assert got == {"client_id": "abc", "scopes": ["a", "b"]}


@pytest.mark.asyncio
async def test_get_missing_returns_none(store, collection):
    assert await store.get("nope", collection=collection) is None


@pytest.mark.asyncio
async def test_delete_returns_true_only_when_row_existed(store, collection):
    await store.put("k", {"v": 1}, collection=collection)
    assert await store.delete("k", collection=collection) is True
    assert await store.delete("k", collection=collection) is False
    assert await store.get("k", collection=collection) is None


@pytest.mark.asyncio
async def test_upsert_overwrites_value_and_ttl(store, collection):
    await store.put("k", {"v": 1}, collection=collection, ttl=60)
    await store.put("k", {"v": 2}, collection=collection)  # no TTL this time
    value, ttl = await store.ttl("k", collection=collection)
    assert value == {"v": 2}
    assert ttl is None


@pytest.mark.asyncio
async def test_ttl_expiry_returns_none_and_cleans_up(store, collection):
    await store.put("k", {"v": "will-expire"}, collection=collection, ttl=0.5)
    assert await store.get("k", collection=collection) == {"v": "will-expire"}

    await asyncio.sleep(0.7)

    # Expired read returns None and lazily deletes the row.
    assert await store.get("k", collection=collection) is None

    async with get_async_db_session() as session:
        remaining = (
            await session.execute(
                delete(MCPOAuthKV)
                .where(col(MCPOAuthKV.collection) == collection)
                .where(col(MCPOAuthKV.key) == "k")
                .returning(col(MCPOAuthKV.key))
            )
        ).all()
    assert remaining == []  # already gone


@pytest.mark.asyncio
async def test_collection_isolation(store):
    col_a = f"a-{uuid.uuid4().hex[:8]}"
    col_b = f"b-{uuid.uuid4().hex[:8]}"
    try:
        await store.put("same-key", {"v": "A"}, collection=col_a)
        await store.put("same-key", {"v": "B"}, collection=col_b)

        assert await store.get("same-key", collection=col_a) == {"v": "A"}
        assert await store.get("same-key", collection=col_b) == {"v": "B"}
    finally:
        async with get_async_db_session() as session:
            await session.execute(
                delete(MCPOAuthKV).where(col(MCPOAuthKV.collection).in_([col_a, col_b]))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_batch_put_get_delete(store, collection):
    keys = ["a", "b", "c"]
    values = [{"v": 1}, {"v": 2}, {"v": 3}]

    await store.put_many(keys, values, collection=collection)

    got = await store.get_many(keys + ["missing"], collection=collection)
    assert got == [{"v": 1}, {"v": 2}, {"v": 3}, None]

    deleted = await store.delete_many(["a", "c", "missing"], collection=collection)
    assert deleted == 2

    got = await store.get_many(keys, collection=collection)
    assert got == [None, {"v": 2}, None]


@pytest.mark.asyncio
async def test_cull_removes_expired_rows(store, collection):
    await store.put("fresh", {"v": 1}, collection=collection, ttl=60)
    await store.put("stale", {"v": 2}, collection=collection, ttl=0.1)
    await asyncio.sleep(0.3)

    await store.cull()

    assert await store.get("fresh", collection=collection) == {"v": 1}
    assert await store.get("stale", collection=collection) is None
