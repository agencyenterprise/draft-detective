"""The heartbeat a RUNNING run writes before its first graph node does.

The job marks a run RUNNING before it prepares the run's state, and the reaper
fails a RUNNING run whose heartbeat goes stale. Beating while the job prepares
keeps a slow setup (loading documents, reading prior state) from looking dead,
while a dead process still stops beating.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from lib.models.workflow_run import TERMINAL_WORKFLOW_RUN_STATUSES
from lib.services.workflow_runs.service import (
    get_workflow_run_status,
    update_workflow_run_heartbeat,
)
from lib.workflows.models import WorkflowCancelledError

# The same cadence as a graph node's supervisor
# (decorators.CANCELLATION_CHECK_INTERVAL), well inside the reaper's 60 s grace.
SETUP_HEARTBEAT_INTERVAL = 5.0


@contextlib.asynccontextmanager
async def heartbeat_while_preparing(workflow_run_id: str) -> AsyncIterator[None]:
    """Keep the run's heartbeat fresh while the runner prepares its state.

    Raises:
        WorkflowCancelledError: On the way out, if the run ended (cancelled, or
            failed by the reaper) or was deleted during setup.
    """
    beat = asyncio.create_task(_beat(workflow_run_id))
    try:
        yield
    finally:
        beat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beat
    status = await get_workflow_run_status(workflow_run_id)
    if status is None or status in TERMINAL_WORKFLOW_RUN_STATUSES:
        raise WorkflowCancelledError(
            f"Workflow run {workflow_run_id} ended or was deleted before its graph started"
        )


async def _beat(workflow_run_id: str) -> None:
    while True:
        await update_workflow_run_heartbeat(workflow_run_id)
        await asyncio.sleep(SETUP_HEARTBEAT_INTERVAL)
