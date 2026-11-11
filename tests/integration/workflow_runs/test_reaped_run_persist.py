"""A reaped run that is still alive must not undo the reaper's cleanup.

The reaper fails a RUNNING run whose heartbeat went stale and persists the
manifest's on_cancel cleanup (pending items become cancelled). The process may
still be alive, though: its nodes take a few seconds to notice FAILED and stop,
and any parallel node that finishes in that window makes the runner persist its
own in-memory state, which still has those items pending.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from langgraph.graph import StateGraph
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.services.workflow_runs import reaper
from lib.services.workflow_runs.service import (
    get_workflow_run,
    persist_workflow_run_state,
)
from lib.workflows.context import ContextSchema
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)
from lib.workflows.runner import run_workflow


@pytest_asyncio.fixture
async def stale_run() -> AsyncIterator[tuple[str, str]]:
    """A RUNNING downloader run whose heartbeat is already past any grace."""
    user = User(
        id=uuid.uuid4(),
        email=f"reaped-run-{uuid.uuid4()}@example.com",
        name="reaped",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(id=uuid.uuid4(), user_id=user.id, title="reaped run")
    long_ago = datetime.utcnow() - timedelta(hours=1)
    run = WorkflowRun(
        id=uuid.uuid4(),
        langgraph_thread_id=str(uuid.uuid4()),
        project_id=project.id,
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        status=WorkflowRunStatus.RUNNING,
        started_at=long_ago,
        heartbeat_at=long_ago,
    )
    for row in (user, project, run):
        async with get_async_db_session() as session:
            session.add(row)
            await session.commit()

    yield str(run.id), str(project.id)

    async with get_async_db_session() as session:
        # Deleting the project cascades to its runs.
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


def _initial_state(project_id: str) -> ReferenceDownloaderState:
    return ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER, project_id=project_id
        ),
        fetched_references=[
            ReferenceFetchResult(reference_id=ref, input_reference=ref)
            for ref in ("r1", "r2")
        ],
    )


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
    """`_reap_once` with a tiny grace, limited to this test's run so it never
    reaps rows that parallel tests own."""
    find = reaper._find_stuck_runs

    async def find_this_run(running: float, pending: float) -> list[WorkflowRun]:
        return [r for r in await find(running, pending) if str(r.id) == run_id]

    with patch.object(reaper, "_find_stuck_runs", new=find_this_run):
        return await reaper._reap_once(running_grace_seconds=0.001)


async def _run_and_reap(run_id: str, project_id: str) -> None:
    steps = _Steps()
    runner = asyncio.create_task(
        run_workflow(
            workflow_run_id=run_id,
            workflow_type=WorkflowRunType.REFERENCE_DOWNLOADER,
            graph=_fan_out_graph(steps),
            state=_initial_state(project_id),
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
        assert await _reap_only(run_id) == 1
        # r1 finishes while r2's supervisor has not yet noticed FAILED...
        steps.reaped.set()
        await asyncio.wait_for(steps.persisted_r1.wait(), timeout=5)
        # ...then the supervisor notices and cancels r2.
        steps.cancel_r2.set()
        await asyncio.wait_for(runner, timeout=5)


@pytest.mark.asyncio
async def test_a_reaped_run_that_is_still_alive_keeps_the_reapers_cleanup(
    stale_run: tuple[str, str],
):
    run_id, project_id = stale_run

    await _run_and_reap(run_id, project_id)

    run = await get_workflow_run(run_id, include_state=True)
    assert run.status == WorkflowRunStatus.FAILED
    assert run.failure_reason == WorkflowRunFailureReason.NO_HEARTBEAT
    statuses = {
        ref["reference_id"]: ref["status"]
        for ref in (run.state_json or {})["fetched_references"]
    }
    # The reaper cancelled both while they were pending. Neither r1's late
    # result nor the runner's failure branch may put them back to pending.
    assert statuses == {"r1": "cancelled", "r2": "cancelled"}
