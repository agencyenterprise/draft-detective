"""The lifespan's queue worker starts again whenever it ends, until cancelled."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from lib.config import task_queue as task_queue_module


async def _raise() -> None:
    raise RuntimeError("listener lost its connection")


async def _return() -> None:
    return None


@pytest.mark.asyncio
@pytest.mark.parametrize("first_run_ends", [_raise, _return], ids=["raises", "returns"])
async def test_a_worker_that_ends_is_started_again_until_cancelled(
    monkeypatch: pytest.MonkeyPatch, first_run_ends: Callable[[], Awaitable[None]]
) -> None:
    runs = 0
    running_again = asyncio.Event()

    async def run_worker_async(**_: Any) -> None:
        nonlocal runs
        runs += 1
        if runs == 1:
            await first_run_ends()
            return
        running_again.set()
        await asyncio.Event().wait()  # runs until cancelled

    monkeypatch.setattr(task_queue_module, "RESTART_DELAY_SECONDS", 0)
    monkeypatch.setattr(
        task_queue_module.task_queue, "run_worker_async", run_worker_async
    )

    worker = asyncio.create_task(task_queue_module._keep_worker_running())
    await asyncio.wait_for(running_again.wait(), timeout=1)
    await task_queue_module._stop_worker(worker)

    assert runs == 2
    assert worker.cancelled()
