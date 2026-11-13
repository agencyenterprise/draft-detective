"""promote_ready_runs against the real database and queue, without a worker:
which runs it queues, parks, releases and cancels."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text, update
from sqlmodel import col

from lib.api.services.workflow_runner import approve_project_gate
from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.projects.service import create_new_revision, get_project_by_id
from lib.services.workflow_runs.gates import approve_gate
from lib.services.workflow_runs.promoter import (
    cancel_run,
    promote_ready_runs,
    waiting_revisions,
)
from lib.services.workflow_runs.reaper import PENDING_GRACE_SECONDS, _find_stuck_runs
from lib.services.workflow_runs.service import (
    fail_workflow_run,
    update_workflow_run_status,
)
from lib.workflows.models import WorkflowGate
from tests.integration.workflow_runs.promoter_support import (
    Scene,
    add_run,
    jobs,
    queued_run_ids,
    start,
    status_of,
)

DOCS = WorkflowRunType.DOCUMENT_PROCESSING
FIGURES = WorkflowRunType.FIGURES_TABLES_CHECK
ABBREVIATIONS = WorkflowRunType.ABBREVIATION_SCAN_V2
CLAIM = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
ASSISTANT = WorkflowRunType.REVIEW_ASSISTANT
CLAIM_PREREQUISITES = (
    DOCS,
    WorkflowRunType.DOCUMENT_SUMMARIZATION,
    WorkflowRunType.REFERENCE_EXTRACTION,
    WorkflowRunType.REFERENCE_FILE_MATCHING,
)

Completed = WorkflowRunStatus.COMPLETED


async def _project(scene: Scene) -> Project:
    project = await get_project_by_id(scene.project_id)
    assert project is not None
    return project


@pytest.mark.asyncio
async def test_a_dependent_is_queued_only_once_its_dependency_completes(scene: Scene):
    docs = await start(scene, DOCS)
    figures = await start(scene, FIGURES)

    await promote_ready_runs(scene.project_id, 1)
    assert await queued_run_ids(scene) == [docs]

    await update_workflow_run_status(docs, Completed)
    await promote_ready_runs(scene.project_id, 1)
    assert await queued_run_ids(scene) == [docs, figures]


@pytest.mark.asyncio
async def test_runs_of_a_type_go_one_at_a_time_under_one_lock(scene: Scene):
    await add_run(scene, DOCS, Completed)
    running = await add_run(scene, FIGURES, WorkflowRunStatus.RUNNING)
    waiting = await start(scene, FIGURES)

    await promote_ready_runs(scene.project_id, 1)
    assert await queued_run_ids(scene) == []

    await update_workflow_run_status(running, Completed)
    await promote_ready_runs(scene.project_id, 1)
    [job] = await jobs(scene)
    assert job.run_id == waiting
    assert job.lock == f"workflow:{scene.project_id}:1:{FIGURES.value}"


@pytest.mark.asyncio
async def test_independent_runs_are_queued_side_by_side_without_a_lock(scene: Scene):
    first = await start(scene, ASSISTANT)
    second = await start(scene, ASSISTANT)

    await promote_ready_runs(scene.project_id, 1)

    assert {job.run_id: job.lock for job in await jobs(scene)} == {
        first: None,
        second: None,
    }


@pytest.mark.asyncio
async def test_a_gate_parks_the_run_once_it_is_the_last_blocker(scene: Scene):
    *ended, _ = CLAIM_PREREQUISITES
    for workflow_type in ended:
        await add_run(scene, workflow_type, Completed)
    matching = await start(scene, WorkflowRunType.REFERENCE_FILE_MATCHING)
    claim = await start(scene, CLAIM)

    await promote_ready_runs(scene.project_id, 1)
    assert await status_of(claim) == WorkflowRunStatus.PENDING

    await update_workflow_run_status(matching, Completed)
    promotion = await promote_ready_runs(scene.project_id, 1)
    assert promotion.parked == [claim]
    assert await status_of(claim) == WorkflowRunStatus.AWAITING_APPROVAL
    assert claim not in await queued_run_ids(scene)


@pytest.mark.asyncio
async def test_approving_the_gate_releases_the_parked_run_and_queues_it_once(
    scene: Scene,
):
    for workflow_type in CLAIM_PREREQUISITES:
        await add_run(scene, workflow_type, Completed)
    claim = await start(scene, CLAIM)
    await promote_ready_runs(scene.project_id, 1)
    assert await status_of(claim) == WorkflowRunStatus.AWAITING_APPROVAL

    released = await approve_project_gate(
        await _project(scene), WorkflowGate.REFERENCE_REVIEW, scene.user
    )
    await approve_project_gate(
        await _project(scene), WorkflowGate.REFERENCE_REVIEW, scene.user
    )

    assert released == [claim]
    assert await status_of(claim) == WorkflowRunStatus.PENDING
    assert await queued_run_ids(scene) == [claim]


@pytest.mark.asyncio
async def test_a_failed_dependency_cancels_its_waiting_dependents(scene: Scene):
    docs = await add_run(scene, DOCS, WorkflowRunStatus.RUNNING)
    figures = await start(scene, FIGURES)
    abbreviations = await start(scene, ABBREVIATIONS)
    assistant = await start(scene, ASSISTANT)

    await fail_workflow_run(
        docs,
        scene.project_id,
        failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
    )
    promotion = await promote_ready_runs(scene.project_id, 1)

    assert set(promotion.cancelled) == {figures, abbreviations}
    assert await status_of(figures) == WorkflowRunStatus.CANCELLED
    assert await queued_run_ids(scene) == [assistant]


@pytest.mark.asyncio
async def test_a_cancelled_dependency_cancels_its_dependents_transitively(scene: Scene):
    runs = {t: await start(scene, t) for t in (*CLAIM_PREREQUISITES, CLAIM)}
    figures = await start(scene, FIGURES)
    await promote_ready_runs(scene.project_id, 1)

    await cancel_run(runs[WorkflowRunType.REFERENCE_EXTRACTION], scene.project_id, 1)

    for workflow_type in (WorkflowRunType.REFERENCE_FILE_MATCHING, CLAIM):
        assert await status_of(runs[workflow_type]) == WorkflowRunStatus.CANCELLED
    assert await status_of(runs[DOCS]) == WorkflowRunStatus.PENDING
    assert await status_of(figures) == WorkflowRunStatus.PENDING


@pytest.mark.asyncio
async def test_cancelling_a_queued_run_drops_its_job(scene: Scene):
    await add_run(scene, DOCS, Completed)
    figures = await start(scene, FIGURES)
    abbreviations = await start(scene, ABBREVIATIONS)
    await promote_ready_runs(scene.project_id, 1)

    await cancel_run(figures, scene.project_id, 1)

    assert await status_of(figures) == WorkflowRunStatus.CANCELLED
    assert {job.run_id: job.status for job in await jobs(scene)} == {
        figures: "cancelled",
        abbreviations: "todo",
    }


@pytest.mark.asyncio
async def test_cancelling_a_running_run_lets_the_next_run_of_its_type_go(scene: Scene):
    await add_run(scene, DOCS, Completed)
    running = await add_run(scene, FIGURES, WorkflowRunStatus.RUNNING)
    waiting = await start(scene, FIGURES)

    await cancel_run(running, scene.project_id, 1)

    assert await status_of(running) == WorkflowRunStatus.CANCELLED
    assert await queued_run_ids(scene) == [waiting]


@pytest.mark.asyncio
async def test_a_new_revision_cancels_the_old_revisions_runs_and_jobs(scene: Scene):
    await add_run(scene, DOCS, Completed)
    figures = await start(scene, FIGURES)
    abbreviations = await add_run(scene, ABBREVIATIONS, WorkflowRunStatus.RUNNING)
    assistant = await add_run(scene, ASSISTANT, WorkflowRunStatus.RUNNING)
    await promote_ready_runs(scene.project_id, 1)

    new_revision, _ = await create_new_revision(scene.project_id, scene.user)

    assert new_revision == 2
    assert await status_of(figures) == WorkflowRunStatus.CANCELLED
    assert await status_of(abbreviations) == WorkflowRunStatus.CANCELLED
    assert await status_of(assistant) == WorkflowRunStatus.RUNNING
    assert [job.status for job in await jobs(scene)] == ["cancelled"]


@pytest.mark.asyncio
async def test_concurrent_passes_queue_each_run_once(scene: Scene):
    await add_run(scene, DOCS, Completed)
    ready = [await start(scene, t) for t in (FIGURES, ABBREVIATIONS, ASSISTANT)]

    promotions = await asyncio.gather(
        *(promote_ready_runs(scene.project_id, 1) for _ in range(5))
    )

    assert sorted(await queued_run_ids(scene)) == sorted(ready)
    assert sorted(r for p in promotions for r in p.queued) == sorted(ready)


@pytest.mark.asyncio
async def test_a_run_released_hours_after_it_parked_gets_a_fresh_reaper_window(
    scene: Scene,
):
    for workflow_type in CLAIM_PREREQUISITES:
        await add_run(scene, workflow_type, Completed)
    claim = await start(scene, CLAIM)
    await promote_ready_runs(scene.project_id, 1)
    long_ago = datetime.utcnow() - timedelta(hours=5)
    async with get_async_db_session() as session:
        await session.execute(
            update(WorkflowRun)
            .where(col(WorkflowRun.id) == claim)
            .values(created_at=long_ago, last_updated_at=long_ago)
        )
        await session.commit()

    await approve_project_gate(
        await _project(scene), WorkflowGate.REFERENCE_REVIEW, scene.user
    )

    stuck = await _find_stuck_runs(60.0, PENDING_GRACE_SECONDS)
    assert claim not in {str(run.id) for run in stuck}


@pytest.mark.asyncio
async def test_more_passes_than_pool_connections_all_finish(scene: Scene):
    """A pass waiting for the revision lock holds one connection; the lock
    holder must not need a second one, or a pool's worth of waiting passes
    starves it."""
    await add_run(scene, DOCS, Completed)
    figures = await start(scene, FIGURES)

    async with asyncio.timeout(30):
        await asyncio.gather(
            *(promote_ready_runs(scene.project_id, 1) for _ in range(25))
        )

    assert await queued_run_ids(scene) == [figures]


@pytest.mark.asyncio
async def test_the_reaper_sweep_queues_a_ready_run_whose_promotion_was_lost(
    scene: Scene,
):
    """A crash between a run's end and its pass, or between a release and its
    job, leaves a ready run with no job. The sweep finds the revision among
    those with waiting runs, and its pass queues the run. (Only this project's
    revision is promoted here: the database is shared with other tests.)"""
    await add_run(scene, DOCS, Completed)
    figures = await start(scene, FIGURES)
    for workflow_type in CLAIM_PREREQUISITES[1:]:
        await add_run(scene, workflow_type, Completed)
    claim = await start(scene, CLAIM)
    await promote_ready_runs(scene.project_id, 1)
    await _drop_jobs(scene)
    # The approval committed, but its pass never ran.
    await approve_gate(scene.project_id, 1, WorkflowGate.REFERENCE_REVIEW)

    assert (scene.project_id, 1) in await waiting_revisions()
    await promote_ready_runs(scene.project_id, 1)

    assert sorted(await queued_run_ids(scene)) == sorted([figures, claim])
    assert await status_of(claim) == WorkflowRunStatus.PENDING


@pytest.mark.asyncio
async def test_a_revision_with_no_waiting_run_is_not_swept(scene: Scene):
    await add_run(scene, DOCS, Completed)

    assert (scene.project_id, 1) not in await waiting_revisions()


async def _drop_jobs(scene: Scene) -> None:
    async with get_async_db_session() as session:
        await session.execute(
            text("DELETE FROM procrastinate_jobs WHERE queue_name = :queue"),
            {"queue": scene.queue},
        )
        await session.commit()
