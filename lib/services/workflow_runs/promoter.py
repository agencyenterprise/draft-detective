"""``promote_ready_runs``: the one place that decides which workflow runs run.

Every event that can change what is ready ends with a call to it: a start, a
gate approval, a run ending (in any status), a cancel and a new revision; the
reaper also promotes every revision with waiting runs, so a ready run whose
promotion was lost (a crash between a run's end and its pass) is still queued.
It is idempotent, so calling it again, or from two processes at once, changes
nothing the first call did not.

A pass holds a transaction-scoped advisory lock on the project revision, so
passes on one revision take turns and each reads what the previous one wrote.
Everything it reads goes through that one transaction, so a pass waiting for
the lock never holds a second connection. Status moves (cascade cancels,
parking behind a gate and releasing from it) commit with the lock; jobs are
queued and cancelled after the commit, so a job never reads a run its pass has
not committed yet. ``plan_promotion`` holds the rules.

A job claims its run through the same pass (``claim_run``): the run starts only
if it is still ready then, so a queued job whose dependency was started again
meanwhile does not run ahead of it.
"""

import logging
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, ColumnElement, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WAITING_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
)
from lib.services.encryption import decrypt_value
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


class ClaimedRun(BaseModel):
    """A run its job may now run (it is RUNNING), with the API key its start
    request named, if any."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run: WorkflowRun
    openai_api_key: str | None


async def promote_ready_runs(project_id: str, revision: int) -> Promotion:
    """Cancel, park, release and queue the revision's waiting runs as they
    stand now (see ``lib.services.workflow_runs.promotion_plan``)."""
    promotion, _ = await _pass(project_id, revision, claim=None)
    return promotion


async def claim_run(workflow_run_id: str) -> ClaimedRun | None:
    """Move the run to RUNNING if it is ready now, in a promoter pass.

    None when it is not: no longer PENDING (cancelled, parked, or started by a
    duplicate job), or held back again (a dependency started anew, a run of its
    type RUNNING). The pass still applies what it found, and a later pass
    queues the run again once it is ready.
    """
    async with get_async_db_session() as session:
        stmt = select(col(WorkflowRun.project_id), col(WorkflowRun.revision)).where(
            col(WorkflowRun.id) == uuid.UUID(workflow_run_id)
        )
        found = (await session.execute(stmt)).one_or_none()
    if found is None or found[0] is None:
        return None
    _, claimed = await _pass(str(found[0]), found[1], claim=uuid.UUID(workflow_run_id))
    return claimed


async def _pass(
    project_id: str, revision: int, claim: uuid.UUID | None
) -> tuple[Promotion, ClaimedRun | None]:
    async with get_async_db_session() as session:
        await session.execute(
            select(func.pg_advisory_xact_lock(_lock_key(project_id, revision)))
        )
        runs = await _revision_runs(session, project_id, revision)
        approved = await get_approved_gates(project_id, revision, session=session)
        plan = plan_promotion(runs, approved)
        promotion = await _apply_status_moves(session, plan)
        claimed = await _claim(session, plan, claim) if claim else None
        to_queue = await _without_running_jobs(session, plan.ready, skip=claim)
        await session.commit()

    for run_id in promotion.cancelled:
        await cancel_queued_job(run_id)
    for run in to_queue:
        if await defer_run_job(run):
            promotion.queued.append(str(run.id))
    if promotion != Promotion():
        logger.info(f"Promoted project {project_id} revision {revision}: {promotion}")
    return promotion, claimed


async def _without_running_jobs(
    session: AsyncSession, ready: list[WorkflowRun], skip: uuid.UUID | None
) -> list[WorkflowRun]:
    """The ready runs to queue: not the one being claimed, nor any whose job a
    worker already took and is about to claim it with (``queueing_lock`` only
    keeps a second job out while the first is still queued)."""
    candidates = [run for run in ready if run.id != skip]
    if not candidates:
        return []
    taken = await session.execute(
        text(
            "SELECT queueing_lock FROM procrastinate_jobs "
            "WHERE status = 'doing' AND queueing_lock = ANY(:run_ids)"
        ),
        {"run_ids": [str(run.id) for run in candidates]},
    )
    busy = set(taken.scalars().all())
    return [run for run in candidates if str(run.id) not in busy]


async def _claim(
    session: AsyncSession, plan: PromotionPlan, run_id: uuid.UUID
) -> ClaimedRun | None:
    """Move the run to RUNNING if the plan has it ready, taking its request's
    API key off the row as it goes."""
    ready = next((run for run in plan.ready if run.id == run_id), None)
    if ready is None:
        return None
    encrypted_key = ready.encrypted_openai_api_key
    stmt = (
        update(WorkflowRun)
        .where(
            col(WorkflowRun.id) == run_id,
            col(WorkflowRun.status) == WorkflowRunStatus.PENDING,
        )
        .values(
            status=WorkflowRunStatus.RUNNING,
            started_at=datetime.utcnow(),
            encrypted_openai_api_key=None,
        )
        .returning(WorkflowRun)
    )
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        return None
    key = decrypt_value(encrypted_key) if encrypted_key else None
    return ClaimedRun(run=run, openai_api_key=key)


async def _apply_status_moves(session: AsyncSession, plan: PromotionPlan) -> Promotion:
    cancelled = await _move(
        session,
        plan.cancel,
        WAITING_WORKFLOW_RUN_STATUSES,
        status=WorkflowRunStatus.CANCELLED,
        completed_at=datetime.utcnow(),
        encrypted_openai_api_key=None,
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


async def promote_waiting_revisions() -> int:
    """Promote every project revision that has a waiting run. The reaper calls
    it on each sweep, so a promotion lost to a crash (between a run's end and
    its pass, or a release and its job) is made up within one sweep, including
    the first sweep after a restart. Returns how many revisions it promoted."""
    revisions = await waiting_revisions()
    for project_id, revision in revisions:
        await promote_ready_runs(project_id, revision)
    return len(revisions)


async def waiting_revisions() -> list[tuple[str, int]]:
    """Every (project, revision) with a PENDING or AWAITING_APPROVAL run."""
    stmt = (
        select(col(WorkflowRun.project_id), col(WorkflowRun.revision))
        .where(
            col(WorkflowRun.status).in_(WAITING_WORKFLOW_RUN_STATUSES),
            col(WorkflowRun.project_id).is_not(None),
        )
        .distinct()
    )
    async with get_async_db_session() as session:
        rows = (await session.execute(stmt)).all()
    return [(str(project_id), revision) for project_id, revision in rows]
