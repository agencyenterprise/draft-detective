"""Periodic sweep that marks heartbeat-less RUNNING and stale PENDING workflows as FAILED.

The dominant cause of "stuck forever" workflow runs is a server restart or OOM
kill that strands the row in RUNNING because the in-process background task
died before the runner's terminal-status update could fire. The reaper is the
self-healing path: any RUNNING row whose heartbeat goes stale is flipped to
FAILED with failure_reason=no_heartbeat, and its dependents are cascade-
cancelled, so dependent workflows don't wait indefinitely.

The reaper also covers PENDING rows that were never picked up (the in-process
background task died before run_workflow was reached, so no heartbeat ever
ticked and wait_for_dependencies never had a chance to time the run out
itself). PENDING rows older than DEPENDENCY_WAIT_TIMEOUT are mechanically
stuck — by then a live runner would have either started them or raised
DependencyWaitTimeoutError on its own.

Multi-pod safe: every pod's lifespan starts its own reaper, but sweeps are
serialized cluster-wide by a Postgres advisory lock (REAPER_ADVISORY_LOCK_KEY).
At most one pod actively sweeps at a time; the rest fail-fast on
pg_try_advisory_lock and skip the tick. The lock is session-scoped, so a
crashed pod cannot strand it.

Wired into FastAPI lifespan in lib/api/main.py.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator

from langchain_core.runnables.config import RunnableConfig
from sqlalchemy import or_, select, text
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
)
from lib.services.workflow_orchestration import DEPENDENCY_WAIT_TIMEOUT
from lib.services.workflow_runs import (
    fail_workflow_run,
    get_workflow_run_state_by_thread_id,
    persist_workflow_run_state,
)
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.registry import create_graph, get_workflow_manifest

logger = logging.getLogger(__name__)

# How often to sweep.
REAPER_INTERVAL_SECONDS = 30.0

# How long a RUNNING row must go without a heartbeat before being reaped.
# Heartbeats tick every CANCELLATION_CHECK_INTERVAL (5s) while any node runs,
# so 60s is 12× the heartbeat interval — comfortable margin for between-node
# gaps, DB blips, and GC pauses without false positives.
REAPER_GRACE_SECONDS = 60.0

# How long a PENDING row may sit before the reaper treats it as orphaned.
# Aligned with DEPENDENCY_WAIT_TIMEOUT: a live runner waiting on dependencies
# would itself raise DependencyWaitTimeoutError at this point and flip the run
# to FAILED, so anything still PENDING past this window was never picked up.
PENDING_GRACE_SECONDS = float(DEPENDENCY_WAIT_TIMEOUT)

# Postgres advisory-lock key — used to serialize reaper sweeps across pods.
# Without this, every pod's lifespan starts its own reaper and N pods each
# do the same sweep every 30s: redundant FAILED writes, redundant cascades,
# N copies of the manifest on_cancel hook appending to the LangGraph
# checkpoint. With the lock, only one pod's sweep runs at a time; others
# fail-fast on pg_try_advisory_lock and skip until the next tick. The key
# is an arbitrary but stable bigint derived from the ASCII bytes "WFREAPER"
# so it won't collide with advisory locks taken by other systems sharing
# the database.
REAPER_ADVISORY_LOCK_KEY = int.from_bytes(b"WFREAPER", "big")


@asynccontextmanager
async def _reaper_advisory_lock() -> AsyncIterator[bool]:
    """Try to acquire the cluster-wide reaper sweep lock.

    Yields ``True`` if this pod owns the sweep for the duration of the
    context, ``False`` if another pod already holds it. The lock is bound
    to the dedicated session opened here; closing the session releases it,
    so a crashed pod cannot strand the lock.
    """
    async with get_async_db_session() as session:
        result = await session.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": REAPER_ADVISORY_LOCK_KEY},
        )
        acquired = bool(result.scalar_one())
        try:
            yield acquired
        finally:
            if acquired:
                await session.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": REAPER_ADVISORY_LOCK_KEY},
                )
                await session.commit()


async def _find_stuck_runs(
    running_grace_seconds: float,
    pending_grace_seconds: float,
) -> list[WorkflowRun]:
    """Return RUNNING rows whose heartbeat is stale and PENDING rows that were
    never picked up.

    Three cases:
      - RUNNING + heartbeat_at IS NULL: never ticked; use started_at as the reference.
      - RUNNING + heartbeat_at < cutoff: ticked once and went silent.
      - PENDING + created_at < pending_cutoff: orphaned before the runner could start it.
    """
    now = datetime.utcnow()
    running_cutoff = now - timedelta(seconds=running_grace_seconds)
    pending_cutoff = now - timedelta(seconds=pending_grace_seconds)
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(
            or_(
                and_(
                    col(WorkflowRun.status) == WorkflowRunStatus.RUNNING,
                    or_(
                        and_(
                            col(WorkflowRun.heartbeat_at).is_(None),
                            col(WorkflowRun.started_at) < running_cutoff,
                        ),
                        col(WorkflowRun.heartbeat_at) < running_cutoff,
                    ),
                ),
                and_(
                    col(WorkflowRun.status) == WorkflowRunStatus.PENDING,
                    col(WorkflowRun.created_at) < pending_cutoff,
                ),
            )
        )
        return list((await session.execute(stmt)).scalars().all())


async def _run_manifest_on_cancel(run: WorkflowRun) -> None:
    """Best-effort invocation of the manifest's on_cancel hook for a stuck run.

    Mirrors the cancel/timeout paths in the runner so per-item statuses (e.g.
    pending validation entries) get cleaned up instead of being stranded as
    'pending'. Errors are logged but never propagated — the reaper must still
    flip the run to FAILED.
    """
    manifest = get_workflow_manifest(run.type, raise_exception=False)
    if manifest is None:
        return

    try:
        state = await get_workflow_run_state_by_thread_id(
            run.langgraph_thread_id, run.type
        )
    except Exception as e:
        logger.error(
            f"Reaper: failed to load state for {run.id}: {e}", exc_info=True
        )
        return

    if state is None:
        return

    thread_config: RunnableConfig = {
        "configurable": {"thread_id": run.langgraph_thread_id}
    }
    try:
        async with get_checkpointer() as checkpointer:
            graph = create_graph(run.type)
            app = graph.compile(checkpointer=checkpointer)
            await manifest.on_cancel(state, app, thread_config)
    except Exception as e:
        logger.error(
            f"Reaper: on_cancel hook failed for {run.id} ({run.type}): {e}",
            exc_info=True,
        )
        return

    # Mirror the cleaned-up state onto state_json so the post-cutover reader
    # path matches what the checkpointer holds. Best-effort: a failure here
    # never blocks the reaper from flipping the run to FAILED.
    try:
        cleaned = await get_workflow_run_state_by_thread_id(
            run.langgraph_thread_id, run.type
        )
        if cleaned is not None:
            await persist_workflow_run_state(str(run.id), cleaned)
    except Exception as e:
        logger.error(
            f"Reaper: failed to mirror post-cancel state for {run.id}: {e}",
            exc_info=True,
        )


async def _reap_once(
    running_grace_seconds: float = REAPER_GRACE_SECONDS,
    pending_grace_seconds: float = PENDING_GRACE_SECONDS,
) -> int:
    """One sweep. Returns the count of reaped runs.

    Serialized cluster-wide via a Postgres advisory lock — a sweep that
    can't acquire the lock returns 0 immediately, leaving the work to
    whichever pod is currently sweeping.
    """
    async with _reaper_advisory_lock() as acquired:
        if not acquired:
            logger.debug(
                "Reaper: another pod holds the sweep lock; skipping this tick"
            )
            return 0
        return await _reap_once_locked(running_grace_seconds, pending_grace_seconds)


async def _reap_once_locked(
    running_grace_seconds: float,
    pending_grace_seconds: float,
) -> int:
    """Inner sweep body — assumes the advisory lock is already held."""
    stuck = await _find_stuck_runs(running_grace_seconds, pending_grace_seconds)
    if not stuck:
        return 0

    for run in stuck:
        if run.project_id is None:
            logger.warning(
                f"Reaper: skipping stuck workflow run {run.id} with no project_id"
            )
            continue

        if run.status == WorkflowRunStatus.PENDING:
            logger.warning(
                f"Reaper: workflow run {run.id} ({run.type}) was PENDING for "
                f">{int(pending_grace_seconds)}s without starting — marking FAILED"
            )
            failure_message = (
                f"PENDING for >{int(pending_grace_seconds)}s without starting; "
                "background task likely crashed before pickup"
            )
        else:
            logger.warning(
                f"Reaper: workflow run {run.id} ({run.type}) has no recent heartbeat — "
                f"marking FAILED"
            )
            failure_message = (
                f"No heartbeat for >{int(running_grace_seconds)}s; "
                "process likely crashed or was restarted"
            )

        try:
            # PENDING runs never reached run_workflow, so there's no checkpoint
            # state for the manifest to clean up; the on_cancel call is a no-op
            # in that case (state is None). Still cheap, and keeps the path
            # uniform.
            await _run_manifest_on_cancel(run)
            await fail_workflow_run(
                str(run.id),
                str(run.project_id),
                failure_reason=WorkflowRunFailureReason.NO_HEARTBEAT,
                failure_message=failure_message,
            )
        except Exception as e:
            # Don't let one bad row stop the sweep.
            logger.error(
                f"Reaper: failed to fail workflow run {run.id}: {e}", exc_info=True
            )

    return len(stuck)


async def run_reaper_loop(
    interval_seconds: float = REAPER_INTERVAL_SECONDS,
    grace_seconds: float = REAPER_GRACE_SECONDS,
    pending_grace_seconds: float = PENDING_GRACE_SECONDS,
) -> None:
    """Long-running sweep loop. Cancel via task.cancel() to stop."""
    logger.info(
        f"Workflow reaper started (interval={interval_seconds}s, "
        f"running_grace={grace_seconds}s, pending_grace={pending_grace_seconds}s)"
    )
    try:
        while True:
            try:
                reaped = await _reap_once(grace_seconds, pending_grace_seconds)
                if reaped:
                    logger.info(f"Reaper: marked {reaped} stuck run(s) as FAILED")
            except Exception as e:
                # Loop must survive transient DB / network errors.
                logger.error(f"Reaper sweep failed: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Workflow reaper stopped")
        raise
