"""Create a workflow run, or join the one already waiting.

Per project, revision and type the database holds at most one RUNNING run and
at most one waiting run (PENDING or AWAITING_APPROVAL); workflows whose
manifest sets ``independent_runs`` are exempt (see the unique indexes on
``WorkflowRun``). A start inserts its waiting run with ``ON CONFLICT DO
NOTHING``; when a waiting run already holds the slot, the start joins it and
creates nothing. So a start while a run is RUNNING queues one run behind it,
and every later start joins that one.

A waiting run is scheduled exactly once: by the start that created it PENDING,
or by whoever moves it from AWAITING_APPROVAL to PENDING, which is one
conditional update that only one caller wins.
"""

import logging
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WAITING_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
)
from lib.services.workflow_runs.gates import (
    claim_run_awaiting_approval,
    get_unsatisfied_gates,
)
from lib.services.workflow_runs.service import get_workflow_run_status
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# Each attempt either creates or joins a run, unless the waiting run left its
# slot (started, released or cancelled) in between; a few cover any real race.
MAX_START_ATTEMPTS = 5


class RunStart(BaseModel):
    """The waiting run that serves a start, and whether that start schedules it."""

    run_id: str
    thread_id: str
    status: WorkflowRunStatus
    # The model the run is to use: the one its row records, so a joined run
    # keeps the model it was created with.
    model: str | None
    # True when this start created the run PENDING or released it from
    # AWAITING_APPROVAL: the caller must schedule it. False when it is parked
    # behind a gate, or someone else already scheduled it.
    schedule: bool
    created: bool


async def start_or_join_run(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
    *,
    model: str | None,
    gated: bool,
) -> RunStart:
    """Create the waiting run of this type, or join the one that exists.

    ``gated`` says whether an unapproved gate holds the workflow back: the run
    is then parked in AWAITING_APPROVAL. Ungated, a joined AWAITING_APPROVAL
    run is released to PENDING, and scheduled by this start if it wins the
    move.
    """
    for _ in range(MAX_START_ATTEMPTS):
        start = await _attempt(project_id, workflow_type, revision, model, gated)
        if start is not None:
            return start
    raise RuntimeError(
        f"Could not create or join a {workflow_type.value} run for project "
        f"{project_id} revision {revision}"
    )


async def _attempt(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
    model: str | None,
    gated: bool,
) -> RunStart | None:
    status = WorkflowRunStatus.AWAITING_APPROVAL if gated else WorkflowRunStatus.PENDING
    created = await _insert_waiting_run(
        project_id, workflow_type, revision, status, model
    )
    if created is not None:
        if gated:
            return await _release_if_gate_approved_meanwhile(created)
        return _start_of(created, schedule=True, created=True)

    waiting = await get_waiting_run(project_id, workflow_type, revision)
    if waiting is None:
        return None  # It left the slot after our insert: try again.
    if waiting.status == WorkflowRunStatus.PENDING or gated:
        return _start_of(waiting, schedule=False, created=False)
    # Parked behind a gate that is approved by now: release it here.
    if await claim_run_awaiting_approval(str(waiting.id)):
        waiting.status = WorkflowRunStatus.PENDING
        return _start_of(waiting, schedule=True, created=False)
    # A concurrent approval released it (it may be running or done by now):
    # this start is served by it. Only a cancelled or deleted run is retried.
    current = await get_workflow_run_status(str(waiting.id))
    if current is None or current == WorkflowRunStatus.CANCELLED:
        return None
    waiting.status = current
    return _start_of(waiting, schedule=False, created=False)


async def _release_if_gate_approved_meanwhile(run: WorkflowRun) -> RunStart:
    """Close the race with a gate approval that read the waiting runs before
    this one was inserted: whichever of the two looks last releases it, and the
    conditional move lets only one of them schedule it."""
    still_gated = await get_unsatisfied_gates(
        str(run.project_id), run.revision, WorkflowRunType(run.type)
    )
    if still_gated:
        return _start_of(run, schedule=False, created=True)
    if await claim_run_awaiting_approval(str(run.id)):
        run.status = WorkflowRunStatus.PENDING
        return _start_of(run, schedule=True, created=True)
    # The approval released it first (or a cancel ended it): report where it
    # is now, so the caller waits on it instead of reporting it as gated.
    run.status = (
        await get_workflow_run_status(str(run.id)) or WorkflowRunStatus.CANCELLED
    )
    return _start_of(run, schedule=False, created=True)


async def _insert_waiting_run(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
    status: WorkflowRunStatus,
    model: str | None,
) -> WorkflowRun | None:
    """Insert the run, or return None when a waiting run already holds the slot.

    Each run gets a fresh thread id; accumulating workflows carry prior state
    forward via prior_self_state (read at execution time in the runner)
    instead of thread reuse.
    """
    stmt = (
        pg_insert(WorkflowRun)
        .values(
            id=uuid.uuid4(),
            project_id=uuid.UUID(project_id),
            type=workflow_type.value,
            langgraph_thread_id=str(uuid.uuid4()),
            status=status,
            revision=revision,
            model=model,
            independent_run=get_workflow_manifest(workflow_type).independent_runs,
        )
        .on_conflict_do_nothing()
        .returning(WorkflowRun)
    )
    async with get_async_db_session() as session:
        run = (await session.execute(stmt)).scalar_one_or_none()
        await session.commit()
    return run


async def get_waiting_run(
    project_id: str, workflow_type: WorkflowRunType, revision: int
) -> WorkflowRun | None:
    """The run of this type waiting to start on the revision, if any."""
    stmt = select(WorkflowRun).where(
        col(WorkflowRun.project_id) == project_id,
        col(WorkflowRun.type) == workflow_type,
        col(WorkflowRun.revision) == revision,
        col(WorkflowRun.status).in_(WAITING_WORKFLOW_RUN_STATUSES),
        col(WorkflowRun.independent_run).is_(False),
    )
    async with get_async_db_session() as session:
        return (await session.execute(stmt)).scalar_one_or_none()


def _start_of(run: WorkflowRun, *, schedule: bool, created: bool) -> RunStart:
    if not created:
        logger.info(f"Joined waiting {run.type} run {run.id} ({run.status.value})")
    return RunStart(
        run_id=str(run.id),
        thread_id=run.langgraph_thread_id,
        status=run.status,
        model=run.model,
        schedule=schedule,
        created=created,
    )
