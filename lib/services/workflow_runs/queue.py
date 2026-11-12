"""The same-type queue: runs of one type on one project revision go one at a time,
first come, first served.

A RUNNING run holds back every other run of its type, and a PENDING run holds
back the PENDING runs created after it (ties broken by id). Runs awaiting
approval hold nothing back until they are released to PENDING.

A run leaves the queue by claiming it: the check that nothing is ahead and the
move to RUNNING happen in one transaction, serialized per project, type and
revision. The claimer is RUNNING from that moment, so a run that becomes
visible later (released from a gate, or committed after a newer one) waits
for it instead of starting alongside it.
"""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    Row,
    Select,
    and_,
    func,
    or_,
    select,
    tuple_,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    TERMINAL_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs.service import (
    get_workflow_run_status,
    update_workflow_run_heartbeat,
)
from lib.workflows.models import WorkflowCancelledError

# How often a claimed run beats while the runner prepares it: the same cadence
# as a graph node's supervisor (decorators.CANCELLATION_CHECK_INTERVAL), well
# inside the reaper's 60 s grace.
SETUP_HEARTBEAT_INTERVAL = 5.0


async def get_run_ahead_in_same_type_queue(workflow_run_id: str) -> WorkflowRun | None:
    """The run that must end before this one: a RUNNING run first, then the
    oldest PENDING run created earlier. None when nothing is ahead, or the run
    no longer exists. Reads only; `claim_same_type_queue_head` is what lets a
    run go."""
    async with get_async_db_session() as session:
        own = await _queue_position(session, workflow_run_id)
        if own is None:
            return None
        return (await session.execute(_run_ahead(own))).scalar_one_or_none()


async def claim_same_type_queue_head(workflow_run_id: str) -> WorkflowRun | None:
    """Move this PENDING run to RUNNING unless a run is ahead of it.

    Returns the run ahead, or None when this run claimed the queue. An advisory
    lock on the project, type and revision makes concurrent claims take turns,
    and each claim's check runs after the lock, so it sees every earlier
    claim's RUNNING row.

    Raises:
        WorkflowCancelledError: If the run no longer exists or already ended
            (cancelled, or failed by the reaper) while it waited.
    """
    async with get_async_db_session() as session:
        own = await _queue_position(session, workflow_run_id)
        if own is None:
            raise _ended(workflow_run_id)
        await session.execute(
            select(
                func.pg_advisory_xact_lock(
                    queue_lock_key(own.project_id, own.type, own.revision)
                )
            )
        )
        run_ahead = (await session.execute(_run_ahead(own))).scalar_one_or_none()
        if run_ahead is None:
            claimed = await session.execute(
                update(WorkflowRun)
                .where(
                    col(WorkflowRun.id) == own.id,
                    col(WorkflowRun.status).in_(
                        (WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING)
                    ),
                )
                .values(
                    status=WorkflowRunStatus.RUNNING,
                    started_at=func.coalesce(
                        col(WorkflowRun.started_at), datetime.utcnow()
                    ),
                )
                .returning(col(WorkflowRun.id))
            )
            if claimed.scalar_one_or_none() is None:
                await session.rollback()
                raise _ended(workflow_run_id)
        await session.commit()
        return run_ahead


def queue_lock_key(
    project_id: uuid.UUID | str, workflow_type: WorkflowRunType | str, revision: int
) -> ColumnElement[int]:
    """The advisory-lock key (a bigint expression) that serializes claims on
    one project, type and revision."""
    key = (
        f"workflow-queue:{project_id}:{WorkflowRunType(workflow_type).value}:{revision}"
    )
    return func.hashtextextended(key, 0, type_=BigInteger)


@contextlib.asynccontextmanager
async def heartbeat_while_preparing(workflow_run_id: str) -> AsyncIterator[None]:
    """Keep a claimed run's heartbeat fresh while the runner prepares its state.

    A claimed run is RUNNING before its first graph node writes a heartbeat,
    and the reaper fails a RUNNING run whose heartbeat goes stale. Beating here
    keeps a slow setup (loading documents, reading prior state) from looking
    dead, while a dead process still stops beating.

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
        raise _ended(workflow_run_id)


async def _beat(workflow_run_id: str) -> None:
    while True:
        await update_workflow_run_heartbeat(workflow_run_id)
        await asyncio.sleep(SETUP_HEARTBEAT_INTERVAL)


def _ended(workflow_run_id: str) -> WorkflowCancelledError:
    return WorkflowCancelledError(
        f"Workflow run {workflow_run_id} ended or was deleted before its graph started"
    )


async def _queue_position(
    session: AsyncSession, workflow_run_id: str
) -> Row[Any] | None:
    stmt = select(
        col(WorkflowRun.created_at),
        col(WorkflowRun.id),
        col(WorkflowRun.project_id),
        col(WorkflowRun.type),
        col(WorkflowRun.revision),
    ).where(col(WorkflowRun.id) == workflow_run_id)
    return (await session.execute(stmt)).one_or_none()


def _run_ahead(own: Row[Any]) -> Select[tuple[WorkflowRun]]:
    is_running = col(WorkflowRun.status) == WorkflowRunStatus.RUNNING
    return (
        select(WorkflowRun)
        .where(
            col(WorkflowRun.project_id) == own.project_id,
            col(WorkflowRun.type) == own.type,
            col(WorkflowRun.revision) == own.revision,
            col(WorkflowRun.id) != own.id,
            or_(
                is_running,
                and_(
                    col(WorkflowRun.status) == WorkflowRunStatus.PENDING,
                    tuple_(col(WorkflowRun.created_at), col(WorkflowRun.id))
                    < tuple_(own.created_at, own.id),
                ),
            ),
        )
        .order_by(is_running.desc(), col(WorkflowRun.created_at))
        .limit(1)
    )
