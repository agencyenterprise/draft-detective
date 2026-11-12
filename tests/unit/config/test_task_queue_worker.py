"""The lifespan's queue worker restarts when it dies and stops when cancelled."""

import asyncio
from typing import Any

import pytest

from lib.config import task_queue as task_queue_module


@pytest.mark.asyncio
async def test_a_worker_that_dies_is_started_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = 0
    running_again = asyncio.Event()

    async def run_worker_async(**_: Any) -> None:
        nonlocal runs
        runs += 1
        if runs == 1:
            raise RuntimeError("listener lost its connection")
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


@pytest.mark.asyncio
async def test_a_worker_that_stops_on_request_is_not_restarted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = 0

    async def run_worker_async(**_: Any) -> None:
        nonlocal runs
        runs += 1

    monkeypatch.setattr(
        task_queue_module.task_queue, "run_worker_async", run_worker_async
    )

    await asyncio.wait_for(task_queue_module._keep_worker_running(), timeout=1)

    assert runs == 1
