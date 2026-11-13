"""The queue jobs that run workflow runs: deferring and cancelling them, and
releasing the ones a dead worker left behind. A job claims its run through the
promoter (``lib.services.workflow_runs.promoter.claim_run``).

One job runs one run (task ``run_workflow``, argument ``workflow_run_id``).
``queueing_lock`` is the run id, so a run waits in the queue at most once;
``lock`` is the run's project, revision and type, so two runs of a type never
execute together, even when a cancelled run's graph is still winding down as
the next one is deferred. Independent runs take no lock: they go side by side.

The job is deferred by name, so this module does not import the task (which
imports the whole runner).
"""

import logging
import uuid

from procrastinate.exceptions import AlreadyEnqueued
from procrastinate.jobs import Status
from sqlalchemy import select
from sqlmodel import col

from lib.config import task_queue as queue_config
from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    TERMINAL_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
)

logger = logging.getLogger(__name__)

RUN_WORKFLOW_TASK = "run_workflow"


def run_job_lock(run: WorkflowRun) -> str | None:
    """The lock that keeps runs of one type apart, or None for independent runs."""
    if run.independent_run:
        return None
    return f"workflow:{run.project_id}:{run.revision}:{run.type}"


async def defer_run_job(run: WorkflowRun) -> bool:
    """Queue the job that runs ``run``. False when it is already queued."""
    deferrer = queue_config.task_queue.configure_task(
        RUN_WORKFLOW_TASK,
        queue=queue_config.WORKFLOW_QUEUE,
        queueing_lock=str(run.id),
        lock=run_job_lock(run),
    )
    try:
        await deferrer.defer_async(workflow_run_id=str(run.id))
    except AlreadyEnqueued:
        return False
    logger.info(f"Queued {run.type} run {run.id}")
    return True


async def cancel_queued_job(workflow_run_id: str) -> None:
    """Drop the run's job if it is still queued; a started job sees the run's
    status and stops on its own."""
    jobs = await queue_config.task_queue.job_manager.list_jobs_async(
        task=RUN_WORKFLOW_TASK, status="todo", queueing_lock=workflow_run_id
    )
    for job in jobs:
        if job.id is not None:
            await queue_config.task_queue.job_manager.cancel_job_by_id_async(job.id)


async def release_stalled_run_jobs() -> list[WorkflowRun]:
    """Fail the jobs whose worker died while running them, so their lock frees.

    A job left ``doing`` by a dead worker (kill -9, OOM) would hold its lock for
    good and no run of its type could start on that project revision again.
    Only jobs whose run has already ended are released: the reaper fails the
    run first (no heartbeat), so a job is never released under a live run.
    Returns the runs whose jobs were released, for the caller to promote.

    A stopgap until stalled jobs are handled by the queue itself.
    """
    stalled = await queue_config.task_queue.job_manager.get_stalled_jobs(
        task_name=RUN_WORKFLOW_TASK
    )
    by_run = {job.queueing_lock: job for job in stalled if job.queueing_lock}
    ended = await _ended_runs(list(by_run))
    for run in ended:
        job_id = by_run[str(run.id)].id
        if job_id is not None:
            await queue_config.task_queue.job_manager.finish_job_by_id_async(
                job_id, status=Status.FAILED, delete_job=False
            )
            logger.warning(f"Released the stalled job of run {run.id}")
    return ended


async def _ended_runs(run_ids: list[str]) -> list[WorkflowRun]:
    if not run_ids:
        return []
    stmt = select(WorkflowRun).where(
        col(WorkflowRun.id).in_([uuid.UUID(run_id) for run_id in run_ids]),
        col(WorkflowRun.status).in_(TERMINAL_WORKFLOW_RUN_STATUSES),
    )
    async with get_async_db_session() as session:
        return list((await session.execute(stmt)).scalars().all())
