"""Waiting for runs to settle, for callers that block on a batch (MCP)."""

import asyncio
import logging
import time

from lib.models.workflow_run import TERMINAL_WORKFLOW_RUN_STATUSES, WorkflowRunStatus
from lib.services.workflow_runs.service import get_workflow_run_status

logger = logging.getLogger(__name__)

SETTLE_POLL_SECONDS = 5.0

# How long a blocking caller waits before it reads whatever statuses the runs
# then have.
SETTLE_TIMEOUT_SECONDS = 2 * 60 * 60

_SETTLED = (*TERMINAL_WORKFLOW_RUN_STATUSES, WorkflowRunStatus.AWAITING_APPROVAL)


async def wait_for_runs_to_settle(
    run_ids: list[str], timeout_seconds: float = SETTLE_TIMEOUT_SECONDS
) -> None:
    """Wait until every run has ended, waits on a gate, or no longer exists."""
    started_at = time.monotonic()
    pending = list(dict.fromkeys(run_ids))
    while pending:
        statuses = [await get_workflow_run_status(run_id) for run_id in pending]
        pending = [
            run_id
            for run_id, status in zip(pending, statuses, strict=True)
            if status is not None and status not in _SETTLED
        ]
        if not pending:
            return
        if time.monotonic() - started_at > timeout_seconds:
            logger.warning(f"Gave up waiting for runs {pending} to settle")
            return
        await asyncio.sleep(SETTLE_POLL_SECONDS)
