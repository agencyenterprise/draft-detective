"""Unit tests for the node supervisor — heartbeat + cancellation polling.

`_supervise_node` is the single mechanism keeping a live, slow node from being
reaped: it bumps `heartbeat_at` every CANCELLATION_CHECK_INTERVAL while the
node runs. If this loop ever stops ticking heartbeats, the reaper will start
killing healthy long-running workflows. These tests guard against that
regression.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.workflow_run import WorkflowRunStatus
from lib.workflows.decorators import _run_node_with_cancellation, _supervise_node


@pytest.mark.asyncio
async def test_supervise_bumps_heartbeat_while_node_runs():
    """While the node task is running, the supervisor calls update_workflow_run_heartbeat each tick."""
    workflow_run_id = "run-1"
    interval = 0.01

    two_heartbeats = asyncio.Event()

    async def heartbeat(_: str) -> None:
        if heartbeat_mock.await_count >= 2:
            two_heartbeats.set()

    # A node that runs until the supervisor has ticked twice. Waiting on the
    # ticks rather than sleeping a few intervals keeps the test from failing
    # when a loaded event loop delays the supervisor's wake-ups.
    async def slow_node():
        await asyncio.wait_for(two_heartbeats.wait(), timeout=5)
        return "ok"

    node_task = asyncio.ensure_future(slow_node())

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.RUNNING),
        ),
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_heartbeat",
            new=AsyncMock(side_effect=heartbeat),
        ) as heartbeat_mock,
    ):
        await asyncio.gather(
            node_task, _supervise_node(workflow_run_id, node_task, interval)
        )

    assert heartbeat_mock.await_count >= 2
    for call in heartbeat_mock.await_args_list:
        assert call.args == (workflow_run_id,)


@pytest.mark.asyncio
async def test_supervise_cancels_node_when_workflow_status_is_cancelled():
    """If the row flips to CANCELLED, the supervisor cancels the node task and stops bumping the heartbeat."""
    workflow_run_id = "run-2"
    interval = 0.01

    async def long_running_node():
        # Long enough that it never finishes on its own — must be cancelled.
        await asyncio.sleep(10)

    node_task = asyncio.ensure_future(long_running_node())

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.CANCELLED),
        ),
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_heartbeat",
            new=AsyncMock(),
        ) as heartbeat_mock,
    ):
        await _supervise_node(workflow_run_id, node_task, interval)

        # Allow the loop to deliver the cancellation
        with pytest.raises(asyncio.CancelledError):
            await node_task

    # When the supervisor sees CANCELLED, it must cancel the node *before*
    # writing a heartbeat — otherwise we'd extend the life of a row that's
    # being torn down.
    heartbeat_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_supervise_cancels_node_when_workflow_status_is_failed():
    """If the reaper flips the row to FAILED, the supervisor must also cancel
    the node — terminal status is terminal status, regardless of how it got
    there. Without this, a reaped run would keep heartbeating and burning
    work after the reaper has already written its tombstone."""
    workflow_run_id = "run-failed"
    interval = 0.01

    async def long_running_node():
        await asyncio.sleep(10)

    node_task = asyncio.ensure_future(long_running_node())

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.FAILED),
        ),
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_heartbeat",
            new=AsyncMock(),
        ) as heartbeat_mock,
    ):
        await _supervise_node(workflow_run_id, node_task, interval)

        with pytest.raises(asyncio.CancelledError):
            await node_task

    heartbeat_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_supervise_returns_when_node_completes_first():
    """Supervisor exits cleanly when the node finishes naturally — no hanging awaits."""
    workflow_run_id = "run-3"
    interval = 0.5  # Much larger than the node's own runtime.

    async def fast_node():
        return "done"

    node_task = asyncio.ensure_future(fast_node())
    # Let the node complete before the supervisor's first sleep wakes up.
    await asyncio.sleep(0)
    await node_task

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run_status",
            new=AsyncMock(),
        ) as status_mock,
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_heartbeat",
            new=AsyncMock(),
        ) as heartbeat_mock,
    ):
        # Supervisor sees node_task.done() at loop top → returns immediately.
        await asyncio.wait_for(
            _supervise_node(workflow_run_id, node_task, interval), timeout=1.0
        )

    status_mock.assert_not_awaited()
    heartbeat_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_node_bumps_heartbeat_even_when_node_finishes_before_first_tick():
    """A node shorter than CANCELLATION_CHECK_INTERVAL still bumps the heartbeat.

    The supervisor only ticks after its first sleep, so a run made of nodes that
    each finish in under 5s would otherwise never set heartbeat_at, and the
    reaper would fail it as no_heartbeat while it is still running.
    """
    workflow_run_id = "run-fast"

    async def fast_node(_state, _runtime):
        await asyncio.sleep(0.01)
        return {"ok": True}

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.RUNNING),
        ),
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_heartbeat",
            new=AsyncMock(),
        ) as heartbeat_mock,
    ):
        result = await _run_node_with_cancellation(
            fast_node, MagicMock(), MagicMock(), workflow_run_id
        )

    assert result == {"ok": True}
    heartbeat_mock.assert_awaited_once_with(workflow_run_id)
