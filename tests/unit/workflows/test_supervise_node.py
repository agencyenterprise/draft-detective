"""Unit tests for the node supervisor — heartbeat + cancellation polling.

`_supervise_node` is the single mechanism keeping a live, slow node from being
reaped: it bumps `heartbeat_at` every CANCELLATION_CHECK_INTERVAL while the
node runs. If this loop ever stops ticking heartbeats, the reaper will start
killing healthy long-running workflows. These tests guard against that
regression.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.workflow_run import WorkflowRunStatus
from lib.workflows.decorators import _supervise_node


@pytest.mark.asyncio
async def test_supervise_bumps_heartbeat_while_node_runs():
    """While the node task is running, the supervisor calls update_workflow_run_heartbeat each tick."""
    workflow_run_id = "run-1"
    interval = 0.01

    # A node that lives long enough for several supervisor ticks.
    async def slow_node():
        await asyncio.sleep(interval * 4)
        return "ok"

    node_task = asyncio.ensure_future(slow_node())

    with (
        patch(
            "lib.services.workflow_runs.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.RUNNING),
        ),
        patch(
            "lib.services.workflow_runs.update_workflow_run_heartbeat",
            new=AsyncMock(),
        ) as heartbeat_mock,
    ):
        await asyncio.gather(node_task, _supervise_node(workflow_run_id, node_task, interval))

    # At least two heartbeats over four intervals — exact count varies with
    # event-loop scheduling, but zero would mean the loop never ticked.
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
            "lib.services.workflow_runs.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.CANCELLED),
        ),
        patch(
            "lib.services.workflow_runs.update_workflow_run_heartbeat",
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
            "lib.services.workflow_runs.get_workflow_run_status", new=AsyncMock()
        ) as status_mock,
        patch(
            "lib.services.workflow_runs.update_workflow_run_heartbeat",
            new=AsyncMock(),
        ) as heartbeat_mock,
    ):
        # Supervisor sees node_task.done() at loop top → returns immediately.
        await asyncio.wait_for(
            _supervise_node(workflow_run_id, node_task, interval), timeout=1.0
        )

    status_mock.assert_not_awaited()
    heartbeat_mock.assert_not_awaited()
