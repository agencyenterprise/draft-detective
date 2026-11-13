"""The run_workflow job on a real queue worker: it claims its run, runs it,
and promotes what the run's end unblocked. The graph is replaced by a fake
that records what ran and ends the run as the test says."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text

from lib.config.database import get_async_db_session
from lib.config.task_queue import task_queue
from lib.models.workflow_run import (
    TERMINAL_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs.jobs import release_stalled_run_jobs
from lib.services.workflow_runs.promoter import (
    cancel_run,
    claim_run,
    promote_ready_runs,
)
from lib.services.workflow_runs.service import update_workflow_run_status
from tests.integration.workflow_runs.promoter_support import (
    Scene,
    add_run,
    jobs,
    start,
    status_of,
    wait_until,
)

DOCS = WorkflowRunType.DOCUMENT_PROCESSING
FIGURES = WorkflowRunType.FIGURES_TABLES_CHECK
EXTRACTION = WorkflowRunType.REFERENCE_EXTRACTION
SUMMARY = WorkflowRunType.DOCUMENT_SUMMARIZATION
MATCHING = WorkflowRunType.REFERENCE_FILE_MATCHING
DOWNLOADER = WorkflowRunType.REFERENCE_DOWNLOADER


class FakeGraph:
    """Stands in for ``execute_claimed_run``: completes each run, except the
    ones it is told to hold, which wait until something ends them (as a node's
    supervisor would see a cancel)."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.hold: set[str] = set()

    async def __call__(self, run: WorkflowRun, openai_api_key: str | None) -> None:
        run_id = str(run.id)
        self.events.append(("start", run_id))
        if run_id in self.hold:
            await wait_until(
                lambda: _ended(run_id),
            )
        else:
            await update_workflow_run_status(run_id, WorkflowRunStatus.COMPLETED)
        self.events.append(("end", run_id))


async def _ended(run_id: str) -> bool:
    return await status_of(run_id) in TERMINAL_WORKFLOW_RUN_STATUSES


@pytest_asyncio.fixture
async def graph(scene: Scene) -> AsyncIterator[FakeGraph]:
    fake = FakeGraph()
    with patch("lib.services.task_queue.tasks.execute_claimed_run", new=fake):
        worker = asyncio.create_task(
            task_queue.run_worker_async(
                queues=[scene.queue],
                concurrency=4,
                install_signal_handlers=False,
                fetch_job_polling_interval=0.2,
            )
        )
        try:
            yield fake
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_the_job_runs_its_run_then_queues_the_dependent(
    scene: Scene, graph: FakeGraph
):
    docs = await start(scene, DOCS)
    figures = await start(scene, FIGURES)

    await promote_ready_runs(scene.project_id, 1)
    await wait_until(lambda: _ended(figures))

    assert graph.events == [
        ("start", docs),
        ("end", docs),
        ("start", figures),
        ("end", figures),
    ]
    assert await status_of(figures) == WorkflowRunStatus.COMPLETED


@pytest.mark.asyncio
async def test_a_cancelled_running_run_ends_before_the_next_of_its_type_starts(
    scene: Scene, graph: FakeGraph
):
    await add_run(scene, DOCS, WorkflowRunStatus.COMPLETED)
    first = await start(scene, FIGURES)
    graph.hold.add(first)
    await promote_ready_runs(scene.project_id, 1)
    await wait_until(lambda: _status_is(first, WorkflowRunStatus.RUNNING))
    second = await start(scene, FIGURES)

    await cancel_run(first, scene.project_id, 1)
    await wait_until(lambda: _ended(second))

    assert await status_of(first) == WorkflowRunStatus.CANCELLED
    assert graph.events == [
        ("start", first),
        ("end", first),
        ("start", second),
        ("end", second),
    ]


@pytest.mark.asyncio
async def test_a_job_whose_run_is_no_longer_pending_does_nothing(scene: Scene):
    run_id = await start(scene, DOCS)

    assert await claim_run(run_id) is not None
    assert await claim_run(run_id) is None
    await update_workflow_run_status(run_id, WorkflowRunStatus.CANCELLED)
    assert await claim_run(run_id) is None


@pytest.mark.asyncio
async def test_a_dead_workers_job_is_released_once_its_run_has_ended(scene: Scene):
    await add_run(scene, DOCS, WorkflowRunStatus.COMPLETED)
    crashed = await start(scene, FIGURES)
    await promote_ready_runs(scene.project_id, 1)
    # A worker took the job and died: the job stays doing, with no worker.
    await _mark_doing_without_worker(scene)
    await claim_run(crashed)

    assert crashed not in [str(r.id) for r in await release_stalled_run_jobs()]

    await update_workflow_run_status(crashed, WorkflowRunStatus.FAILED)
    released = await release_stalled_run_jobs()

    assert crashed in [str(run.id) for run in released]
    assert [job.status for job in await jobs(scene)] == ["failed"]


async def _status_is(run_id: str, status: WorkflowRunStatus) -> bool:
    return await status_of(run_id) == status


async def _mark_doing_without_worker(scene: Scene) -> None:
    async with get_async_db_session() as session:
        await session.execute(
            text(
                "UPDATE procrastinate_jobs SET status = 'doing', worker_id = NULL "
                "WHERE queue_name = :queue"
            ),
            {"queue": scene.queue},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_a_queued_run_whose_required_dependency_starts_again_is_not_claimed(
    scene: Scene,
):
    await add_run(scene, DOCS, WorkflowRunStatus.COMPLETED)
    figures = await start(scene, FIGURES)
    await promote_ready_runs(scene.project_id, 1)
    rerun = await start(scene, DOCS)
    await promote_ready_runs(scene.project_id, 1)

    assert await claim_run(figures) is None
    assert await status_of(figures) == WorkflowRunStatus.PENDING

    await update_workflow_run_status(rerun, WorkflowRunStatus.COMPLETED)
    await promote_ready_runs(scene.project_id, 1)
    assert await claim_run(figures) is not None


@pytest.mark.asyncio
async def test_a_queued_run_whose_optional_dependency_starts_is_not_claimed(
    scene: Scene,
):
    for workflow_type in (DOCS, SUMMARY, EXTRACTION):
        await add_run(scene, workflow_type, WorkflowRunStatus.COMPLETED)
    downloader = await start(scene, DOWNLOADER)
    await promote_ready_runs(scene.project_id, 1)
    matching = await start(scene, MATCHING)

    assert await claim_run(downloader) is None
    assert await status_of(matching) == WorkflowRunStatus.PENDING
    assert await status_of(downloader) == WorkflowRunStatus.PENDING


@pytest.mark.asyncio
async def test_the_request_key_reaches_the_job_once_and_leaves_the_row(scene: Scene):
    docs = await start(scene, DOCS, api_key="sk-request")

    claimed = await claim_run(docs)

    assert claimed is not None and claimed.openai_api_key == "sk-request"
    assert (await _row(docs)).encrypted_openai_api_key is None


@pytest.mark.asyncio
async def test_a_run_that_ends_unclaimed_drops_the_request_key(scene: Scene):
    docs = await start(scene, DOCS, api_key="sk-request")

    await cancel_run(docs, scene.project_id, 1)

    assert (await _row(docs)).encrypted_openai_api_key is None


async def _row(run_id: str) -> WorkflowRun:
    async with get_async_db_session() as session:
        run = await session.get(WorkflowRun, uuid.UUID(run_id))
    assert run is not None
    return run
