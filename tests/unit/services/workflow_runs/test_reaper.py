"""Unit tests for the workflow reaper sweep logic."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs import reaper as workflow_reaper
from lib.services.workflow_runs.promoter import promote_waiting_revisions
from lib.services.workflow_runs.reaper import (
    PENDING_GRACE_SECONDS,
    REAPER_GRACE_SECONDS,
    _reap_once,
    _run_manifest_on_cancel,
    run_reaper_loop,
)


@asynccontextmanager
async def _fake_lock(acquired: bool):
    yield acquired


@pytest.fixture(autouse=True)
def _stub_advisory_lock():
    """Default stub: lock is acquired so the existing assertions exercise the
    full sweep body. Tests that need the lock-not-acquired path patch the
    helper themselves.
    """
    with (
        patch.object(
            workflow_reaper,
            "_reaper_advisory_lock",
            lambda: _fake_lock(True),
        ),
        # The sweep's queue steps, stubbed so no test reaches a database.
        patch.object(
            workflow_reaper, "release_stalled_run_jobs", new=AsyncMock(return_value=[])
        ),
        patch.object(
            workflow_reaper, "promote_waiting_revisions", new=AsyncMock(return_value=0)
        ),
        patch.object(workflow_reaper, "promote_ready_runs", new=AsyncMock()),
    ):
        yield


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
    """Hook is awaited with the loaded state and its cleaned state is returned
    for fail_workflow_run to store with FAILED."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    state = MagicMock()
    cleaned_state = MagicMock()
    manifest = MagicMock()
    manifest.on_cancel = AsyncMock(return_value=cleaned_state)

    with (
        patch.object(workflow_reaper, "get_workflow_manifest", return_value=manifest),
        # State is read from state_json via read_workflow_run_state.
        patch.object(
            workflow_reaper,
            "read_workflow_run_state",
            new=AsyncMock(return_value=state),
        ),
    ):
        result = await _run_manifest_on_cancel(run)

    manifest.on_cancel.assert_awaited_once_with(state)
    assert result is cleaned_state


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_noop_when_manifest_missing():
    """No state load is attempted when the workflow type has no manifest."""
    run = _make_run(WorkflowRunStatus.PENDING)

    state_loader = AsyncMock()

    with (
        patch.object(workflow_reaper, "get_workflow_manifest", return_value=None),
        patch.object(workflow_reaper, "read_workflow_run_state", new=state_loader),
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
        patch.object(workflow_reaper, "get_workflow_manifest", return_value=manifest),
        patch.object(
            workflow_reaper,
            "read_workflow_run_state",
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
        patch.object(workflow_reaper, "get_workflow_manifest", return_value=manifest),
        patch.object(
            workflow_reaper,
            "read_workflow_run_state",
            new=AsyncMock(return_value=MagicMock()),
        ),
    ):
        assert await _run_manifest_on_cancel(run) is None


@pytest.mark.asyncio
async def test_run_manifest_on_cancel_swallows_state_load_exception():
    """A failure loading state is logged and the hook is skipped, not re-raised."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    manifest = MagicMock()
    manifest.on_cancel = AsyncMock()

    with (
        patch.object(workflow_reaper, "get_workflow_manifest", return_value=manifest),
        patch.object(
            workflow_reaper,
            "read_workflow_run_state",
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

    on_cancel.assert_not_awaited()  # handed to fail_workflow_run, which is mocked
    fail.assert_awaited_once()
    kwargs = fail.await_args.kwargs
    args = fail.await_args.args
    assert args[0] == str(run.id)
    assert args[1] == str(run.project_id)
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.NO_HEARTBEAT
    assert "No heartbeat" in kwargs["failure_message"]
    assert "60s" in kwargs["failure_message"]
    assert kwargs["clean_up_state"] is on_cancel


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
async def test_reap_once_cleans_up_inside_the_failed_transition():
    """The on_cancel cleanup goes to fail_workflow_run, which stores it in the
    same transaction as FAILED: no FAILED run with pending items in between,
    and no runner write between the cleanup and FAILED."""
    run = _make_run(WorkflowRunStatus.RUNNING)
    fail = AsyncMock()

    with (
        patch.object(
            workflow_reaper, "_find_stuck_runs", new=AsyncMock(return_value=[run])
        ),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
    ):
        await _reap_once()

    assert fail.await_args.kwargs["clean_up_state"] is _run_manifest_on_cancel


@pytest.mark.asyncio
async def test_reap_once_continues_when_one_row_fails():
    """A bad row's failure does not stop the rest of the sweep."""
    bad = _make_run(WorkflowRunStatus.RUNNING)
    good = _make_run(WorkflowRunStatus.RUNNING)

    fail = AsyncMock(side_effect=[RuntimeError("transient"), None])

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
        call.args[0]: call.kwargs["failure_message"] for call in fail.await_args_list
    }
    assert "No heartbeat" in messages_by_id[str(running.id)]
    assert "PENDING for" in messages_by_id[str(pending.id)]


# ---------------------------------------------------------------------------
# Sanity defaults
# ---------------------------------------------------------------------------


def test_default_grace_windows_are_consistent():
    """Pending grace must be >= running grace; otherwise PENDING reaping is overly aggressive."""
    assert PENDING_GRACE_SECONDS >= REAPER_GRACE_SECONDS


# ---------------------------------------------------------------------------
# Advisory lock — multi-pod serialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reap_once_skips_when_lock_not_acquired():
    """If another pod holds the advisory lock, this sweep returns 0 and does no DB work."""
    find_stuck = AsyncMock(return_value=[_make_run(WorkflowRunStatus.RUNNING)])
    fail = AsyncMock()
    on_cancel = AsyncMock()

    with (
        patch.object(
            workflow_reaper,
            "_reaper_advisory_lock",
            lambda: _fake_lock(False),
        ),
        patch.object(workflow_reaper, "_find_stuck_runs", new=find_stuck),
        patch.object(workflow_reaper, "fail_workflow_run", new=fail),
        patch.object(workflow_reaper, "_run_manifest_on_cancel", new=on_cancel),
    ):
        reaped = await _reap_once()

    assert reaped == 0
    find_stuck.assert_not_awaited()
    fail.assert_not_awaited()
    on_cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_reaper_loop_log_does_not_claim_skipped_runs_were_failed(caplog):
    """_reap_once counts every stuck run found, skipped ones included, so the
    loop's log must not report that count as runs marked FAILED."""
    with (
        patch.object(workflow_reaper, "_reap_once", new=AsyncMock(return_value=1)),
        patch.object(
            workflow_reaper.asyncio,
            "sleep",
            new=AsyncMock(side_effect=asyncio.CancelledError),
        ),
        caplog.at_level(logging.INFO, logger=workflow_reaper.logger.name),
        pytest.raises(asyncio.CancelledError),
    ):
        await run_reaper_loop()

    assert "found 1 stuck run(s)" in caplog.text
    assert "as FAILED" not in caplog.text


@pytest.mark.asyncio
async def test_released_stalled_jobs_promote_each_revision_once():
    """A dead worker's jobs are released after the sweep, and each revision
    they belonged to is promoted once, so the next run of the type can go."""
    released = [
        _make_run(
            WorkflowRunStatus.FAILED, run_type=WorkflowRunType.FIGURES_TABLES_CHECK
        ),
        _make_run(
            WorkflowRunStatus.FAILED, run_type=WorkflowRunType.ABBREVIATION_SCAN_V2
        ),
    ]
    with (
        patch(
            "lib.services.workflow_runs.reaper.release_stalled_run_jobs",
            new=AsyncMock(return_value=released),
        ),
        patch(
            "lib.services.workflow_runs.reaper.promote_ready_runs", new=AsyncMock()
        ) as promote,
    ):
        await workflow_reaper._release_stalled_jobs()

    promote.assert_awaited_once_with("project-1", 1)


@pytest.mark.asyncio
async def test_a_failing_release_does_not_stop_the_sweep():
    with patch(
        "lib.services.workflow_runs.reaper.release_stalled_run_jobs",
        new=AsyncMock(side_effect=RuntimeError("queue down")),
    ):
        await workflow_reaper._release_stalled_jobs()


@pytest.mark.asyncio
async def test_the_sweep_promotes_every_waiting_revision():
    """So a promotion a crash lost is made up within one sweep."""
    with (
        patch(
            "lib.services.workflow_runs.promoter.waiting_revisions",
            new=AsyncMock(return_value=[("p1", 1), ("p2", 3)]),
        ),
        patch(
            "lib.services.workflow_runs.promoter.promote_ready_runs", new=AsyncMock()
        ) as promote,
    ):
        await promote_waiting_revisions()

    assert [c.args for c in promote.await_args_list] == [("p1", 1), ("p2", 3)]
