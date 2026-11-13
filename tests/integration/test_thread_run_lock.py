"""One run at a time per thread, across workers: the Postgres advisory lock.

Within a process, runs on one thread queue in memory before connecting; across
processes, on the advisory lock. A second connection stands in for another worker.
"""

import asyncio
import uuid

import pytest
from psycopg import AsyncConnection

from lib.agents.checkpointer import (
    THREAD_LOCK_CONNECTIONS,
    one_run_per_thread,
)
from lib.agents.checkpointer import THREAD_LOCK_SEED as SEED
from lib.config.env import config as env


async def hold(thread_id: str, name: str, order: list[str]) -> None:
    async with one_run_per_thread(thread_id):
        order.append(f"{name} in")
        await asyncio.sleep(0.2)
        order.append(f"{name} out")


@pytest.mark.asyncio
async def test_two_runs_on_one_thread_take_turns() -> None:
    thread = f"test-{uuid.uuid4()}"
    order: list[str] = []

    await asyncio.gather(hold(thread, "first", order), hold(thread, "second", order))

    assert order in (
        ["first in", "first out", "second in", "second out"],
        ["second in", "second out", "first in", "first out"],
    )


@pytest.mark.asyncio
async def test_runs_on_different_threads_do_not_wait() -> None:
    order: list[str] = []

    await asyncio.gather(
        hold(f"test-{uuid.uuid4()}", "first", order),
        hold(f"test-{uuid.uuid4()}", "second", order),
    )

    assert set(order[:2]) == {"first in", "second in"}


@pytest.mark.asyncio
async def test_a_run_that_fails_releases_its_thread() -> None:
    thread = f"test-{uuid.uuid4()}"

    with pytest.raises(RuntimeError):
        async with one_run_per_thread(thread):
            raise RuntimeError("the run broke")

    async with asyncio.timeout(5), one_run_per_thread(thread):
        pass


@pytest.mark.asyncio
async def test_a_run_waits_for_another_workers_run_on_its_thread() -> None:
    """Another worker is another connection holding the same key."""

    thread = f"test-{uuid.uuid4()}"
    other_worker = await AsyncConnection.connect(env.DATABASE_URL, autocommit=True)
    key = "hashtextextended(%s, %s)"
    await other_worker.execute(f"SELECT pg_advisory_lock({key})", (thread, SEED))
    entered = asyncio.Event()

    async def run() -> None:
        async with one_run_per_thread(thread):
            entered.set()

    waiting = asyncio.create_task(run())
    await asyncio.sleep(0.3)
    assert not entered.is_set()

    await other_worker.close()
    async with asyncio.timeout(5):
        await waiting


@pytest.mark.asyncio
async def test_a_process_holds_a_bounded_number_of_lock_connections() -> None:
    inside = most = 0

    async def run() -> None:
        nonlocal inside, most
        async with one_run_per_thread(f"test-{uuid.uuid4()}"):
            inside += 1
            most = max(most, inside)
            await asyncio.sleep(0.1)
            inside -= 1

    await asyncio.gather(*(run() for _ in range(THREAD_LOCK_CONNECTIONS * 2)))

    assert most == THREAD_LOCK_CONNECTIONS
