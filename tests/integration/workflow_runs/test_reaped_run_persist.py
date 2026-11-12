"""A reaped run that is still alive must not undo the reaper's cleanup.

The reaper fails a RUNNING run whose heartbeat went stale and persists the
manifest's on_cancel cleanup (pending items become cancelled). The process may
still be alive, though: its nodes take a few seconds to notice FAILED and stop,
and any parallel node that finishes in that window makes the runner persist its
own in-memory state, which still has those items pending.
"""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.graph import StateGraph
from sqlalchemy import update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.services.workflow_runs import reaper
from lib.services.workflow_runs.service import (
    fail_workflow_run,
    get_workflow_run,
    persist_workflow_run_state,
    update_workflow_run_status,
)
from lib.workflows.context import ContextSchema
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)
from lib.workflows.runner import run_workflow
from tests.integration.workflow_runs.reaped_run_support import initial_state


class _Steps:
    """The moments the test drives: the reap, then r2's supervisor cancel."""

    def __init__(self) -> None:
        self.reaped = asyncio.Event()
        self.persisted_r1 = asyncio.Event()
        self.cancel_r2 = asyncio.Event()


def _fan_out_graph(steps: _Steps) -> StateGraph:
    """Two parallel fetches: r1 finishes once the run is reaped, and r2 is
    cancelled afterwards, the way its supervisor cancels it on seeing FAILED."""

    async def fetch_r1(state: ReferenceDownloaderState) -> dict:
        await steps.reaped.wait()
        done = ReferenceFetchResult(
            reference_id="r1",
            input_reference="r1",
            status=ReferenceFetchStatus.COMPLETED,
        )
        return {"fetched_references": [done]}

    async def fetch_r2(state: ReferenceDownloaderState) -> dict:
        await steps.cancel_r2.wait()
        # LangGraph turns this into NodeCancelledError, an Exception, so the
        # runner ends through its failure branch.
        raise asyncio.CancelledError

    graph = StateGraph(ReferenceDownloaderState)
    graph.add_node("fetch_r1", fetch_r1)
    graph.add_node("fetch_r2", fetch_r2)
    graph.add_edge("__start__", "fetch_r1")
    graph.add_edge("__start__", "fetch_r2")
    return graph


async def _wait_for_state(run_id: str) -> None:
    for _ in range(200):
        if (await get_workflow_run(run_id, include_state=True)).state_json:
            return
        await asyncio.sleep(0.025)
    raise AssertionError("the runner never persisted its first state")


def _signal_r1_persisted(steps: _Steps) -> Any:
    """Wrap the runner's state persist to signal once it handled r1's result."""

    async def persist(run_id: str, state: Any, **kwargs: Any) -> None:
        await persist_workflow_run_state(run_id, state, **kwargs)
        if any(
            ref.status == ReferenceFetchStatus.COMPLETED
            for ref in state.fetched_references
        ):
            steps.persisted_r1.set()

    return patch("lib.workflows.runner.persist_workflow_run_state", new=persist)


async def _reap_only(run_id: str) -> int:
    """One reaper sweep with a tiny grace, limited to this test's run so it
    never reaps rows that parallel tests own. It skips the cluster-wide sweep
    lock, which a parallel test's sweep may be holding."""
    find = reaper._find_stuck_runs

    async def find_this_run(running: float, pending: float) -> list[WorkflowRun]:
        return [r for r in await find(running, pending) if str(r.id) == run_id]

    with patch.object(reaper, "_find_stuck_runs", new=find_this_run):
        return await reaper._reap_once_locked(
            running_grace_seconds=0.001,
            pending_grace_seconds=reaper.PENDING_GRACE_SECONDS,
        )


def _finish_r1_just_before_the_reapers_fail(steps: _Steps) -> Any:
    """Let r1 finish and persist while the reaper is about to write FAILED."""
    fail = reaper.fail_workflow_run

    async def finish_r1_then_fail(*args: Any, **kwargs: Any) -> None:
        steps.reaped.set()
        await asyncio.wait_for(steps.persisted_r1.wait(), timeout=5)
        await fail(*args, **kwargs)

    return patch.object(reaper, "fail_workflow_run", new=finish_r1_then_fail)


async def _run_and_reap(
    run_id: str, project_id: str, *, r1_finishes_before_fail: bool
) -> None:
    steps = _Steps()
    runner = asyncio.create_task(
        run_workflow(
            workflow_run_id=run_id,
            workflow_type=WorkflowRunType.REFERENCE_DOWNLOADER,
            graph=_fan_out_graph(steps),
            state=initial_state(project_id),
            context=ContextSchema(
                project_id=project_id,
                workflow_run_id=run_id,
                file_artifacts_service=MockFileArtifactsService(),
            ),
            thread_id=str(uuid.uuid4()),
        )
    )
    with _signal_r1_persisted(steps):
        await _wait_for_state(run_id)
        if r1_finishes_before_fail:
            with _finish_r1_just_before_the_reapers_fail(steps):
                assert await _reap_only(run_id) == 1
        else:
            assert await _reap_only(run_id) == 1
            # r1 finishes while r2's supervisor has not yet noticed FAILED...
            steps.reaped.set()
            await asyncio.wait_for(steps.persisted_r1.wait(), timeout=5)
        # ...then the supervisor notices and cancels r2.
        steps.cancel_r2.set()
        await asyncio.wait_for(runner, timeout=5)


async def _reaped_statuses(run_id: str) -> dict[str, str]:
    run = await get_workflow_run(run_id, include_state=True)
    assert run.status == WorkflowRunStatus.FAILED
    assert run.failure_reason == WorkflowRunFailureReason.NO_HEARTBEAT
    return {
        ref["reference_id"]: ref["status"]
        for ref in (run.state_json or {})["fetched_references"]
    }


@pytest.mark.asyncio
async def test_a_reaped_run_that_is_still_alive_keeps_the_reapers_cleanup(
    stale_run: tuple[str, str],
):
    run_id, project_id = stale_run

    await _run_and_reap(run_id, project_id, r1_finishes_before_fail=False)

    # The reaper cancelled both while they were pending. Neither r1's late
    # result nor the runner's failure branch may put them back to pending.
    assert await _reaped_statuses(run_id) == {"r1": "cancelled", "r2": "cancelled"}


@pytest.mark.asyncio
async def test_a_node_finishing_just_before_the_reap_is_kept_and_the_rest_cleaned(
    stale_run: tuple[str, str],
):
    run_id, project_id = stale_run

    await _run_and_reap(run_id, project_id, r1_finishes_before_fail=True)

    # r1's result landed while the run was still RUNNING, so it stays; the
    # reaper's cleanup, written after FAILED, still cancels r2.
    assert await _reaped_statuses(run_id) == {"r1": "completed", "r2": "cancelled"}


@pytest.mark.asyncio
async def test_a_node_finishing_after_a_user_cancel_still_saves_its_result(
    stale_run: tuple[str, str],
):
    """A user cancel is the runner's to clean up, not the reaper's: when the
    last node finishes before its supervisor sees CANCELLED, the graph ends
    normally and that final snapshot is the only record of the result."""
    run_id, project_id = stale_run
    cancelled = asyncio.Event()

    async def fetch_all(state: ReferenceDownloaderState) -> dict:
        await cancelled.wait()
        done = [
            ReferenceFetchResult(
                reference_id=ref,
                input_reference=ref,
                status=ReferenceFetchStatus.COMPLETED,
            )
            for ref in ("r1", "r2")
        ]
        return {"fetched_references": done}

    graph = StateGraph(ReferenceDownloaderState)
    graph.add_node("fetch_all", fetch_all)
    graph.add_edge("__start__", "fetch_all")
    runner = asyncio.create_task(
        run_workflow(
            workflow_run_id=run_id,
            workflow_type=WorkflowRunType.REFERENCE_DOWNLOADER,
            graph=graph,
            state=initial_state(project_id),
            context=ContextSchema(
                project_id=project_id,
                workflow_run_id=run_id,
                file_artifacts_service=MockFileArtifactsService(),
            ),
            thread_id=str(uuid.uuid4()),
        )
    )
    await _wait_for_state(run_id)
    async with get_async_db_session() as session:
        await session.execute(
            update(WorkflowRun)
            .where(col(WorkflowRun.id) == run_id)
            .values(status=WorkflowRunStatus.CANCELLED)
        )
        await session.commit()
    cancelled.set()
    await asyncio.wait_for(runner, timeout=5)

    run = await get_workflow_run(run_id, include_state=True)
    assert run.status == WorkflowRunStatus.CANCELLED
    statuses = {
        ref["reference_id"]: ref["status"]
        for ref in (run.state_json or {})["fetched_references"]
    }
    assert statuses == {"r1": "completed", "r2": "completed"}


@pytest.mark.asyncio
async def test_the_reapers_cleanup_is_skipped_when_the_run_already_ended(
    stale_run: tuple[str, str],
):
    """The cleanup rides on the FAILED write, so a run that completed before the
    reaper got to it keeps its state untouched."""
    run_id, project_id = stale_run
    await persist_workflow_run_state(run_id, initial_state(project_id))
    await update_workflow_run_status(run_id, WorkflowRunStatus.COMPLETED)
    clean_up = AsyncMock()

    await fail_workflow_run(
        run_id,
        project_id,
        failure_reason=WorkflowRunFailureReason.NO_HEARTBEAT,
        clean_up_state=clean_up,
    )

    clean_up.assert_not_awaited()
    assert (await get_workflow_run(run_id)).status == WorkflowRunStatus.COMPLETED
