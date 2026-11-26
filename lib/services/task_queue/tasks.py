"""Tasks the job queue runs.

`run_workflow` runs one workflow run: `promote_ready_runs` queues it once the
run is ready (see `lib.services.workflow_runs.jobs`). `ping` exists so the
queue can be checked end to end: defer it, and a worker in any API process
runs it once.
"""

import logging

from lib.config.task_queue import task_queue
from lib.services.workflow_runs.jobs import RUN_WORKFLOW_TASK
from lib.services.workflow_runs.promoter import claim_run, promote_ready_runs
from lib.workflows.runner import execute_claimed_run

logger = logging.getLogger(__name__)


@task_queue.task(name="ping")
async def ping(message: str) -> str:
    """Log the message and return it, so a test can see which job ran."""
    logger.info("task queue ping: %s", message)
    return message


@task_queue.task(name=RUN_WORKFLOW_TASK)
async def run_workflow(workflow_run_id: str) -> None:
    """Claim the run if it is still ready, run it to its end, then promote what
    its end unblocked.

    The terminal status is written before the promoter runs, and this job still
    holds the type's lock meanwhile, so the next run of the type it queues
    starts only once this one has fully finished.
    """
    claimed = await claim_run(workflow_run_id)
    if claimed is None:
        logger.info(f"Run {workflow_run_id} is not ready to run; nothing to do")
        return
    run = claimed.run
    try:
        await execute_claimed_run(run, openai_api_key=claimed.openai_api_key)
    finally:
        await promote_ready_runs(str(run.project_id), run.revision)
