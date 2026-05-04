"""Unit tests for the workflow reaper sweep logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services import workflow_reaper
from lib.services.workflow_reaper import (
    PENDING_GRACE_SECONDS,
    REAPER_GRACE_SECONDS,
    _reap_once,
    _run_manifest_on_cancel,
)


def _make_run(
    status: WorkflowRunStatus,
    *,
    project_id: str | None = "project-1",
    run_type: WorkflowRunType = WorkflowRunType.DOCUMENT_PROCESSING,
) -> WorkflowRun:
    return WorkflowRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        type=run_type,
        status=status,
        langgraph_thread_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# _run_manifest_on_cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_invokes_hook_when_state_present():
    """Hook is awaited with (state, app, thread_config) when both manifest and state exist."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    state = MagicMock()
    manifest = MagicMock()
    manifest.on_cancel = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "get_workflow_manifest", return_value=manifest
        ),
        patch.object(
            workflow_reaper,
            "get_workflow_run_state_by_thread_id",
            new=AsyncMock(return_value=state),
        ),
        patch.object(
            workflow_reaper, "create_graph", return_value=MagicMock()
        ) as mock_create_graph,
        patch.object(workflow_reaper, "get_checkpointer") as mock_checkpointer_cm,
    ):
        mock_checkpointer_cm.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock()
        )
        mock_checkpointer_cm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_create_graph.return_value.compile.return_value = MagicMock()

        await _run_manifest_on_cancel(run)

    manifest.on_cancel.assert_awaited_once()
    awaited_state, awaited_app, awaited_config = manifest.on_cancel.await_args.args
    assert awaited_state is state
    assert awaited_config["configurable"]["thread_id"] == run.langgraph_thread_id


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_noop_when_manifest_missing():
    """No state load is attempted when the workflow type has no manifest."""
    run = _make_run(WorkflowRunStatus.PENDING)

    state_loader = AsyncMock()

    with (
        patch.object(workflow_reaper, "get_workflow_manifest", return_value=None),
        patch.object(
            workflow_reaper, "get_workflow_run_state_by_thread_id", new=state_loader
        ),
    ):
        await _run_manifest_on_cancel(run)

    state_loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_noop_when_state_missing():
    """Hook is skipped when no checkpoint state exists (e.g. orphaned PENDING)."""
    run = _make_run(WorkflowRunStatus.PENDING)
    manifest = MagicMock()
    manifest.on_cancel = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "get_workflow_manifest", return_value=manifest
        ),
        patch.object(
            workflow_reaper,
            "get_workflow_run_state_by_thread_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        await _run_manifest_on_cancel(run)

    manifest.on_cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_swallows_hook_exception():
    """A raising on_cancel hook is logged but does not propagate."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    manifest = MagicMock()
    manifest.on_cancel = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch.object(
            workflow_reaper, "get_workflow_manifest", return_value=manifest
        ),
        patch.object(
            workflow_reaper,
            "get_workflow_run_state_by_thread_id",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch.object(
            workflow_reaper, "create_graph", return_value=MagicMock()
        ) as mock_create_graph,
        patch.object(workflow_reaper, "get_checkpointer") as mock_checkpointer_cm,
    ):
        mock_checkpointer_cm.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock()
        )
        mock_checkpointer_cm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_create_graph.return_value.compile.return_value = MagicMock()

        await _run_manifest_on_cancel(run)


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_swallows_state_load_exception():
    """A failure loading state is logged and the hook is skipped, not re-raised."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    manifest = MagicMock()
    manifest.on_cancel = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "get_workflow_manifest", return_value=manifest
        ),
        patch.object(
            workflow_reaper,
            "get_workflow_run_state_by_thread_id",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ),
    ):
        await _run_manifest_on_cancel(run)

    manifest.on_cancel.assert_not_awaited()


# ---------------------------------------------------------------------------
# _reap_once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reap_once_returns_zero_when_nothing_stuck():
    """No stuck runs → no fail_workflow_run calls, returns 0."""
    fail = AsyncMock()
    with (
        patch.object(
            workflow_reaper, "_find_stuck_runs", new=AsyncMock(return_value=[])
        ),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=AsyncMock()),
    ):
        reaped = await _reap_once()

    assert reaped == 0
    fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_reap_once_skips_runs_without_project_id():
    """Stuck rows with no project_id are logged and skipped, not failed."""
    run = _make_run(WorkflowRunStatus.RUNNING, project_id=None)
    fail = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "_find_stuck_runs", new=AsyncMock(return_value=[run])
        ),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=AsyncMock()),
    ):
        reaped = await _reap_once()

    # The total still counts the row (it was discovered as stuck), but no
    # fail_workflow_run call is made.
    assert reaped == 1
    fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_reap_once_running_uses_no_heartbeat_failure_reason():
    """RUNNING stuck rows get failure_reason=NO_HEARTBEAT and the heartbeat-shaped message."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    fail = AsyncMock()
    on_cancel = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "_find_stuck_runs", new=AsyncMock(return_value=[run])
        ),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=on_cancel),
    ):
        await _reap_once(running_grace_seconds=60.0)

    on_cancel.assert_awaited_once_with(run)
    fail.assert_awaited_once()
    kwargs = fail.await_args.kwargs
    args = fail.await_args.args
    assert args[0] == str(run.id)
    assert args[1] == str(run.project_id)
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.NO_HEARTBEAT
    assert "No heartbeat" in kwargs["failure_message"]
    assert "60s" in kwargs["failure_message"]


@pytest.mark.asyncio
async def test_reap_once_pending_uses_pending_specific_message():
    """PENDING stuck rows get NO_HEARTBEAT reason but a PENDING-specific message."""
    run = _make_run(WorkflowRunStatus.PENDING)
    fail = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "_find_stuck_runs", new=AsyncMock(return_value=[run])
        ),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=AsyncMock()),
    ):
        await _reap_once(pending_grace_seconds=PENDING_GRACE_SECONDS)

    fail.assert_awaited_once()
    kwargs = fail.await_args.kwargs
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.NO_HEARTBEAT
    msg = kwargs["failure_message"]
    assert "PENDING for" in msg
    assert "without starting" in msg
    assert str(int(PENDING_GRACE_SECONDS)) in msg


@pytest.mark.asyncio
async def test_reap_once_calls_on_cancel_before_fail():
    """The manifest hook fires before the FAILED transition so cleanup happens first."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    call_order: list[str] = []

    async def record_on_cancel(_run):
        call_order.append("on_cancel")

    async def record_fail(*_args, **_kwargs):
        call_order.append("fail")

    with (
        patch.object(
            workflow_reaper, "_find_stuck_runs", new=AsyncMock(return_value=[run])
        ),
        patch.object(
            workflow_reaper, "_run_manifest_on_cancel", new=AsyncMock(side_effect=record_on_cancel)
        ),
        patch.object(
            workflow_reaper, "fail_workflow_run", new=AsyncMock(side_effect=record_fail)
        ),
    ):
        await _reap_once()

    assert call_order == ["on_cancel", "fail"]


@pytest.mark.asyncio
async def test_reap_once_continues_when_one_row_fails():
    """A bad row's failure does not stop the rest of the sweep."""
    bad = _make_run(WorkflowRunStatus.RUNNING)
    good = _make_run(WorkflowRunStatus.RUNNING)

    fail = AsyncMock(
        side_effect=[RuntimeError("transient"), None]
    )

    with (
        patch.object(
            workflow_reaper,
            "_find_stuck_runs",
            new=AsyncMock(return_value=[bad, good]),
        ),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=AsyncMock()),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
    ):
        reaped = await _reap_once()

    assert reaped == 2
    assert fail.await_count == 2
    assert fail.await_args_list[1].args[0] == str(good.id)


@pytest.mark.asyncio
async def test_reap_once_handles_mixed_running_and_pending():
    """A sweep with both RUNNING and PENDING stuck rows produces distinct messages."""
    running = _make_run(WorkflowRunStatus.RUNNING)
    pending = _make_run(WorkflowRunStatus.PENDING)
    fail = AsyncMock()

    with (
        patch.object(
            workflow_reaper,
            "_find_stuck_runs",
            new=AsyncMock(return_value=[running, pending]),
        ),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=AsyncMock()),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
    ):
        await _reap_once()

    assert fail.await_count == 2
    messages_by_id = {
        call.args[0]: call.kwargs["failure_message"]
        for call in fail.await_args_list
    }
    assert "No heartbeat" in messages_by_id[str(running.id)]
    assert "PENDING for" in messages_by_id[str(pending.id)]


# ---------------------------------------------------------------------------
# Sanity defaults
# ---------------------------------------------------------------------------


def test_default_grace_windows_are_consistent():
    """Pending grace must be >= running grace; otherwise PENDING reaping is overly aggressive."""
    assert PENDING_GRACE_SECONDS >= REAPER_GRACE_SECONDS
