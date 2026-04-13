"""Unit tests for the shared checkpointer pool.

Langgraph's AsyncPostgresSaver must be backed by a single shared psycopg pool
(bounded per-process), with a fresh saver created per call so concurrent
workflow runs don't contend on a global checkpoint lock.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from lib.workflows import checkpointer as checkpointer_module
from lib.workflows.checkpointer import (
    checkpointer_pool,
    close_checkpointer_pool,
    get_checkpointer,
)


@pytest.fixture(autouse=True)
def reset_pool_state():
    """Reset module-level _opened flag and mock the DB-touching calls."""
    checkpointer_module._opened = False
    with (
        patch.object(checkpointer_pool, "open", new_callable=AsyncMock) as mock_open,
        patch.object(checkpointer_pool, "close", new_callable=AsyncMock) as mock_close,
        patch(
            "lib.workflows.checkpointer.AsyncPostgresSaver.setup",
            new_callable=AsyncMock,
        ) as mock_setup,
    ):
        yield mock_open, mock_close, mock_setup
    checkpointer_module._opened = False


@pytest.mark.asyncio
async def test_savers_share_the_pool():
    """Every get_checkpointer() call yields a saver bound to the shared pool."""
    async with get_checkpointer() as saver_a:
        async with get_checkpointer() as saver_b:
            assert saver_a.conn is checkpointer_pool
            assert saver_b.conn is checkpointer_pool


@pytest.mark.asyncio
async def test_savers_are_distinct_instances():
    """Each call yields a fresh saver so per-saver asyncio.Lock doesn't
    globally serialize concurrent workflow runs."""
    async with get_checkpointer() as saver_a:
        async with get_checkpointer() as saver_b:
            assert saver_a is not saver_b
            assert saver_a.lock is not saver_b.lock


@pytest.mark.asyncio
async def test_pool_opened_and_setup_run_only_once(reset_pool_state):
    """Back-to-back calls must not re-open the pool or re-run migrations."""
    mock_open, _, mock_setup = reset_pool_state

    async with get_checkpointer():
        pass
    async with get_checkpointer():
        pass
    async with get_checkpointer():
        pass

    assert mock_open.await_count == 1
    assert mock_setup.await_count == 1


@pytest.mark.asyncio
async def test_pool_opened_once_under_concurrency(reset_pool_state):
    """The double-checked lock must hold under simultaneous first-use calls."""
    mock_open, _, mock_setup = reset_pool_state

    async def use_checkpointer():
        async with get_checkpointer() as saver:
            return saver

    savers = await asyncio.gather(*[use_checkpointer() for _ in range(20)])

    assert len(savers) == 20
    assert all(s.conn is checkpointer_pool for s in savers)
    assert mock_open.await_count == 1
    assert mock_setup.await_count == 1


@pytest.mark.asyncio
async def test_close_allows_reopen(reset_pool_state):
    """After close_checkpointer_pool, the next call re-opens and re-runs setup."""
    mock_open, mock_close, mock_setup = reset_pool_state

    async with get_checkpointer():
        pass
    assert mock_open.await_count == 1
    assert mock_setup.await_count == 1

    await close_checkpointer_pool()
    assert mock_close.await_count == 1

    async with get_checkpointer():
        pass
    assert mock_open.await_count == 2
    assert mock_setup.await_count == 2


@pytest.mark.asyncio
async def test_close_without_open_is_noop(reset_pool_state):
    """Closing before anything was opened must not call pool.close()."""
    _, mock_close, _ = reset_pool_state

    await close_checkpointer_pool()

    assert mock_close.await_count == 0
