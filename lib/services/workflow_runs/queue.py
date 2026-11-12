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

from datetime import datetime
from typing import Any

from sqlalchemy import Row, Select, and_, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus


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

    Returns the run ahead, or None when this run claimed the queue (or no
    longer exists). An advisory lock on the project, type and revision makes
    concurrent claims take turns, and each claim's check runs after the lock,
    so it sees every earlier claim's RUNNING row.
    """
    async with get_async_db_session() as session:
        own = await _queue_position(session, workflow_run_id)
        if own is None:
            return None
        queue_key = f"workflow-queue:{own.project_id}:{own.type}:{own.revision}"
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(queue_key, 0)))
        )
        run_ahead = (await session.execute(_run_ahead(own))).scalar_one_or_none()
        if run_ahead is None:
            await session.execute(
                update(WorkflowRun)
                .where(
                    col(WorkflowRun.id) == own.id,
                    col(WorkflowRun.status) == WorkflowRunStatus.PENDING,
                )
                .values(status=WorkflowRunStatus.RUNNING, started_at=datetime.utcnow())
            )
        await session.commit()
        return run_ahead


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
