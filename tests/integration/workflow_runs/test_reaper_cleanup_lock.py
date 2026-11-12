"""The reaper's cleanup and FAILED commit together, and a runner write that
races them waits on the row lock and then skips.

The other reaped-run tests put the runner's write before or after the reap;
this one puts it in the middle of the reaper's transaction, which is what the
row lock in update_workflow_run_status is for.
"""

import asyncio

import pytest
from sqlalchemy import text

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
)
from lib.services.workflow_runs.service import (
    fail_workflow_run,
    get_workflow_run,
    persist_workflow_run_state,
)
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)
from tests.integration.workflow_runs.reaped_run_support import initial_state


def _with_r1(
    state: ReferenceDownloaderState, status: ReferenceFetchStatus
) -> ReferenceDownloaderState:
    r1 = ReferenceFetchResult(reference_id="r1", input_reference="r1", status=status)
    return state.model_copy(update={"fetched_references": [r1]})


async def _wait_until_a_state_write_waits_on_a_lock() -> None:
    """Wait until some backend's UPDATE of a run's state_json is blocked."""
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE cardinality(pg_blocking_pids(pid)) > 0 "
        "AND query ILIKE 'UPDATE workflow_run%state_json%'"
    )
    for _ in range(200):
        async with get_async_db_session() as session:
            if (await session.execute(query)).scalar_one():
                return
        await asyncio.sleep(0.025)
    raise AssertionError("the runner's write never waited on the reaper's row lock")


def _statuses(run: WorkflowRun) -> dict[str, str]:
    refs = (run.state_json or {})["fetched_references"]
    return {ref["reference_id"]: ref["status"] for ref in refs}


@pytest.mark.asyncio
async def test_a_runner_write_racing_the_reapers_cleanup_waits_then_skips(
    stale_run: tuple[str, str],
):
    run_id, project_id = stale_run
    pending = initial_state(project_id)
    await persist_workflow_run_state(run_id, pending)
    holding_lock = asyncio.Event()
    release = asyncio.Event()

    async def slow_clean_up(run: WorkflowRun) -> ReferenceDownloaderState:
        # Runs inside the reaper's transaction, with the row locked.
        holding_lock.set()
        await release.wait()
        return _with_r1(pending, ReferenceFetchStatus.CANCELLED)

    reap = asyncio.create_task(
        fail_workflow_run(
            run_id,
            project_id,
            failure_reason=WorkflowRunFailureReason.NO_HEARTBEAT,
            clean_up_state=slow_clean_up,
        )
    )
    await asyncio.wait_for(holding_lock.wait(), timeout=5)

    # The runner finishes r1 while the reaper holds the row.
    runner_write = asyncio.create_task(
        persist_workflow_run_state(
            run_id,
            _with_r1(pending, ReferenceFetchStatus.COMPLETED),
            unless_failed=True,
        )
    )
    await _wait_until_a_state_write_waits_on_a_lock()
    assert not runner_write.done()

    # Readers still see the run as it was: neither write has committed.
    during = await get_workflow_run(run_id, include_state=True)
    assert during.status == WorkflowRunStatus.RUNNING
    assert _statuses(during) == {"r1": "pending", "r2": "pending"}

    release.set()
    await asyncio.wait_for(asyncio.gather(reap, runner_write), timeout=5)

    # FAILED and the cleanup landed together; the runner's write then saw a
    # FAILED row and skipped, so r1 stays cancelled rather than completed.
    after = await get_workflow_run(run_id, include_state=True)
    assert after.status == WorkflowRunStatus.FAILED
    assert _statuses(after) == {"r1": "cancelled"}
