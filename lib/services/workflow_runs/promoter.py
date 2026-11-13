"""``promote_ready_runs``: the one place that decides which workflow runs run.

Every event that can change what is ready ends with a call to it: a start, a
gate approval, a run ending (in any status), a cancel and a new revision. It is
idempotent, so calling it again, or from two processes at once, changes nothing
the first call did not.

A pass holds a transaction-scoped advisory lock on the project revision, so
passes on one revision take turns and each reads what the previous one wrote.
Status moves (cascade cancels, parking behind a gate and releasing from it)
commit with the lock; jobs are queued and cancelled after the commit, so a job
never reads a run its pass has not committed yet. ``plan_promotion`` holds the
rules.
"""

import logging
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import BigInteger, ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WAITING_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
)
from lib.services.workflow_runs.gates import get_approved_gates
from lib.services.workflow_runs.jobs import cancel_queued_job, defer_run_job
from lib.services.workflow_runs.promotion_plan import PromotionPlan, plan_promotion
from lib.services.workflow_runs.service import cancel_workflow_run

logger = logging.getLogger(__name__)


class Promotion(BaseModel):
    """The run ids one pass moved, by what it did with them."""

    queued: list[str] = []
    parked: list[str] = []
    released: list[str] = []
    cancelled: list[str] = []


async def promote_ready_runs(project_id: str, revision: int) -> Promotion:
    """Cancel, park, release and queue the revision's waiting runs as they
    stand now (see ``lib.services.workflow_runs.promotion_plan``)."""
    async with get_async_db_session() as session:
        await session.execute(
            select(func.pg_advisory_xact_lock(_lock_key(project_id, revision)))
        )
        runs = await _revision_runs(session, project_id, revision)
        plan = plan_promotion(runs, await get_approved_gates(project_id, revision))
        promotion = await _apply_status_moves(session, plan)
        await session.commit()

    for run_id in promotion.cancelled:
        await cancel_queued_job(run_id)
    for run in plan.ready:
        if await defer_run_job(run):
            promotion.queued.append(str(run.id))
    if promotion != Promotion():
        logger.info(f"Promoted project {project_id} revision {revision}: {promotion}")
    return promotion


async def _apply_status_moves(session: AsyncSession, plan: PromotionPlan) -> Promotion:
    now = datetime.utcnow()
    cancelled = await _move(
        session,
        plan.cancel,
        WAITING_WORKFLOW_RUN_STATUSES,
        status=WorkflowRunStatus.CANCELLED,
        completed_at=now,
    )
    parked = await _move(
        session,
        plan.park,
        (WorkflowRunStatus.PENDING,),
        status=WorkflowRunStatus.AWAITING_APPROVAL,
    )
    released = await _move(
        session,
        plan.release,
        (WorkflowRunStatus.AWAITING_APPROVAL,),
        status=WorkflowRunStatus.PENDING,
    )
    if cancelled:
        logger.info(f"Cancelled runs whose required dependency ended: {cancelled}")
    return Promotion(parked=parked, released=released, cancelled=cancelled)


async def _move(
    session: AsyncSession,
    runs: list[WorkflowRun],
    from_statuses: tuple[WorkflowRunStatus, ...],
    **values: object,
) -> list[str]:
    """Write ``values`` on the runs still in one of ``from_statuses``, so a
    terminal status written meanwhile (a cancel, the reaper) stays."""
    if not runs:
        return []
    stmt = (
        update(WorkflowRun)
        .where(
            col(WorkflowRun.id).in_([run.id for run in runs]),
            col(WorkflowRun.status).in_(from_statuses),
        )
        .values(**values)
        .returning(col(WorkflowRun.id))
    )
    return [str(run_id) for run_id in (await session.execute(stmt)).scalars().all()]


async def _revision_runs(
    session: AsyncSession, project_id: str, revision: int
) -> list[WorkflowRun]:
    stmt = select(WorkflowRun).where(
        col(WorkflowRun.project_id) == uuid.UUID(project_id),
        col(WorkflowRun.revision) == revision,
    )
    return list((await session.execute(stmt)).scalars().all())


def _lock_key(project_id: str, revision: int) -> ColumnElement[int]:
    key = f"workflow-promoter:{project_id}:{revision}"
    return func.hashtextextended(key, 0, type_=BigInteger)


async def cancel_run(workflow_run_id: str, project_id: str, revision: int) -> None:
    """Cancel a run as a user does: mark it CANCELLED (a RUNNING run's node
    supervisor then stops its graph), drop its job if still queued, and promote,
    which cancels its waiting required-dependents and lets the next run of its
    type go."""
    await cancel_workflow_run(workflow_run_id, project_id)
    await cancel_queued_job(workflow_run_id)
    await promote_ready_runs(project_id, revision)
