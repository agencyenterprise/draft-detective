"""One run at a time per thread, across workers: the Postgres advisory lock.

Two holders here are two connections, which is what two workers would be.
"""

import asyncio
import uuid

import pytest

from lib.agents.checkpointer import one_run_per_thread


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

    assert order[:2] == ["first in", "second in"]


@pytest.mark.asyncio
async def test_a_run_that_fails_releases_its_thread() -> None:
    thread = f"test-{uuid.uuid4()}"

    with pytest.raises(RuntimeError):
        async with one_run_per_thread(thread):
            raise RuntimeError("the run broke")

    async with asyncio.timeout(5), one_run_per_thread(thread):
        pass
