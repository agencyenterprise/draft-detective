import asyncio
import logging
from enum import StrEnum
from datetime import datetime
from typing import List, Optional, Type, cast

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select, update
from sqlalchemy.orm import undefer
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import (
    ACTIVE_WORKFLOW_RUN_STATUSES,
    TERMINAL_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.text_sanitization import sanitize_for_postgres
from lib.services.workflow_cost.breakdown import CostBreakdown
from lib.services.workflow_cost.extractor import walk_state_for_usage
from lib.services.workflow_cost.pricing import compute_cost
from lib.services.workflow_progress import cancel_workflow_progress
from lib.workflows.dependency_resolver import get_required_dependents
from lib.workflows.models import is_user_visible_workflow
from lib.workflows.registry import get_workflow_manifest, is_available_workflow_type
from lib.workflows.workflow_types import WorkflowState

logger = logging.getLogger(__name__)


class WorkflowStateStatus(StrEnum):
    """Why a run's state is or isn't available to render.

    `state` alone cannot express this: it is None both for a run that never
    persisted state and for one whose persisted state no longer matches the
    current model. The UI needs to tell those apart — the first is "nothing to
    show", the second is "your data is here but the assessment changed".
    """

    OK = "ok"
    # No state_json on the row: the run never got far enough, or predates the
    # state_json backfill.
    ABSENT = "absent"
    # state_json is present but no longer validates against the workflow's
    # current state model, i.e. the assessment changed since this run.
    SCHEMA_MISMATCH = "schema_mismatch"


class WorkflowRunDetail(BaseModel):
    run: WorkflowRun
    state: WorkflowState | None
    cost: CostBreakdown | None = None
    state_status: WorkflowStateStatus = WorkflowStateStatus.OK


async def _compute_cost_for_state(
    state: WorkflowState | None,
) -> CostBreakdown | None:
    if state is None:
        return None
    try:
        records = walk_state_for_usage(state)
        if not records:
            return None
        return await compute_cost(records)
    except Exception as e:  # pragma: no cover — never let cost calc break the response
        logger.warning(f"Failed to compute workflow cost: {e}")
        return None


async def persist_workflow_run_state(
    workflow_run_id: str, state: WorkflowState
) -> None:
    """Snapshot the workflow state onto the WorkflowRun row.

    Called after every node yield in the runner so a crashed/cancelled run still
    has its last-good state inspectable on the row itself. `state_json` is the
    single source of truth for workflow state.
    """
    payload = sanitize_for_postgres(state.model_dump(mode="json"))
    async with get_async_db_session() as session:
        stmt = (
            update(WorkflowRun)
            .where(col(WorkflowRun.id) == workflow_run_id)
            .values(state_json=payload)
        )
        await session.execute(stmt)
        await session.commit()


def hydrate_workflow_run_state(run: WorkflowRun) -> WorkflowState | None:
    """Reconstruct a WorkflowState from the row's persisted state_json.

    Returns None when state_json is missing (pre-backfill rows), when the run's
    workflow type is no longer registered, or when the persisted shape no longer
    matches the current WorkflowState subclass. Callers that need to tell those
    apart should use `hydrate_workflow_run_state_with_status`.
    """
    return hydrate_workflow_run_state_with_status(run)[0]


def hydrate_workflow_run_state_with_status(
    run: WorkflowRun,
) -> tuple[WorkflowState | None, WorkflowStateStatus]:
    """`hydrate_workflow_run_state`, plus why the state is unavailable.

    Hydration is attempted once and the outcome reported, so callers that render
    a reason do not pay for a second validation pass over what can be a
    multi-megabyte payload.
    """
    if run.state_json is None:
        return None, WorkflowStateStatus.ABSENT
    manifest = get_workflow_manifest(run.type, raise_exception=False)
    if manifest is None:
        # Retired workflow type still present in old rows. Callers that pass
        # include_internal=True see these runs (is_user_visible_workflow filters
        # them out for everyone else), so a missing manifest has to degrade to a
        # stateless row instead of failing every read on the project — including
        # create_state, which would otherwise block starting any new workflow.
        logger.warning(
            f"No workflow manifest registered for type {run.type!r} "
            f"(run {run.id}); returning no state for it."
        )
        return None, WorkflowStateStatus.ABSENT
    state_type = cast(Type[WorkflowState], manifest.get_state_type())
    try:
        return state_type(**run.state_json), WorkflowStateStatus.OK
    except Exception as e:
        logger.warning(
            f"Error hydrating state_json for run {run.id} "
            f"(possibly an old state schema version): {e}"
        )
        return None, WorkflowStateStatus.SCHEMA_MISMATCH


async def read_workflow_run_state(run: WorkflowRun) -> WorkflowState | None:
    """Single read path for a run's workflow state, hydrated from `state_json`.

    `run` must have been loaded with `state_json` undeferred (see the model's
    deferred-strategy note in lib/models/workflow_run.py) so this stays an
    in-memory hydrate rather than an illegal async lazy-load on a detached row.
    """
    return hydrate_workflow_run_state(run)


async def get_workflow_run(
    workflow_run_id: str, user: Optional[User] = None, include_state: bool = False
) -> WorkflowRun:
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun, Project)
            .outerjoin(Project)
            .where(col(WorkflowRun.id) == workflow_run_id)
        )
        if include_state:
            # state_json is deferred by default; load it in-session so callers
            # can hydrate it after this session closes (no async lazy-load).
            stmt = stmt.options(undefer(col(WorkflowRun.state_json)))  # type: ignore[arg-type]  # SQLModel Mapped[...] is a QueryableAttribute at runtime
        result = (await session.execute(stmt)).one_or_none()

    if result is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    run, project = result.tuple()

    if user is not None and project is not None and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return run


async def create_workflow_run(
    project_id: str,
    status: WorkflowRunStatus,
    type: WorkflowRunType,
    thread_id: str,
    revision: int = 1,
) -> str:
    """Create a new workflow run record."""
    now = datetime.utcnow()
    async with get_async_db_session() as session:
        run = WorkflowRun(
            langgraph_thread_id=thread_id,
            project_id=project_id,
            status=status,
            type=type,
            revision=revision,
            completed_at=now if status == WorkflowRunStatus.COMPLETED else None,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
    return str(run.id)


async def update_workflow_run_status(
    workflow_run_id: str,
    status: WorkflowRunStatus,
    failure_reason: Optional[WorkflowRunFailureReason] = None,
    failure_message: Optional[str] = None,
) -> None:
    """Update an existing workflow run's status. Never overwrites a terminal status.

    Terminal statuses (CANCELLED, COMPLETED, FAILED) are write-once. Without
    this guard the runner's COMPLETED write could clobber a FAILED row the
    reaper just produced (race window: heartbeat lag → reap → runner finishes
    its last node → COMPLETED write), and racing failure paths could
    overwrite each other's failure_reason / failure_message. The guard is
    application-level (SELECT-then-UPDATE inside one transaction); when two
    pods race, last writer wins for non-terminal transitions, which is
    benign because non-terminal writes are idempotent.

    `failure_reason` and `failure_message` are persisted only when transitioning
    to FAILED; they are ignored for other statuses.
    """
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(
            and_(
                col(WorkflowRun.id) == workflow_run_id,
                col(WorkflowRun.status).not_in(TERMINAL_WORKFLOW_RUN_STATUSES),
            )
        )
        run = (await session.execute(stmt)).scalar_one_or_none()
        if run:
            now = datetime.utcnow()
            run.status = status
            if status == WorkflowRunStatus.RUNNING and run.started_at is None:
                run.started_at = now
            if status in TERMINAL_WORKFLOW_RUN_STATUSES:
                run.completed_at = now
            if status == WorkflowRunStatus.FAILED:
                run.failure_reason = failure_reason
                run.failure_message = (
                    failure_message[:2000] if failure_message else None
                )
            await session.commit()


async def update_workflow_run_heartbeat(workflow_run_id: str) -> None:
    """Bump heartbeat_at for a workflow run.

    Cheap, called frequently from the node decorator so the reaper can tell a
    progressing run from a stuck one. Does not affect status or last_updated_at
    semantics — heartbeat is intentionally distinct so "status changed" vs
    "node ticked" remain separable.
    """
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == workflow_run_id)
        run = (await session.execute(stmt)).scalar_one_or_none()
        if run:
            run.heartbeat_at = datetime.utcnow()
            await session.commit()


async def get_workflow_run_status(workflow_run_id: str) -> WorkflowRunStatus | None:
    """Lightweight fetch of just the status for a workflow run. Used for cancellation checks."""
    async with get_async_db_session() as session:
        stmt = select(col(WorkflowRun.status)).where(
            col(WorkflowRun.id) == workflow_run_id
        )
        return (await session.execute(stmt)).scalar_one_or_none()


async def cancel_workflow_run(workflow_run_id: str, project_id: str) -> None:
    """
    Cancel a workflow run and recursively cancel any active runs that depend on it.

    Only cascades through required_dependencies — optional dependents are left running
    since they handle missing data by design.
    """
    run = await get_workflow_run(workflow_run_id)
    if run.project_id is None:
        raise ValueError(f"Workflow run {workflow_run_id} has no project_id")
    await cancel_workflow_progress(run.project_id, run.type)
    await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.CANCELLED)
    await _cascade_cancel_dependents(run.type, project_id, run.revision)


async def fail_workflow_run(
    workflow_run_id: str,
    project_id: str,
    failure_reason: WorkflowRunFailureReason,
    failure_message: Optional[str] = None,
) -> None:
    """Mark a workflow run as FAILED and cascade-cancel its active dependents.

    Used for unrecoverable workflow-level halts (timeout, dependency timeout,
    no heartbeat, unhandled exception). From a dependent's perspective a failed
    parent is equivalent to a cancelled one — there is no salvageable output —
    so we cascade to CANCELLED rather than FAILED.
    """
    run = await get_workflow_run(workflow_run_id)
    if run.project_id is None:
        raise ValueError(f"Workflow run {workflow_run_id} has no project_id")
    await cancel_workflow_progress(run.project_id, run.type)
    await update_workflow_run_status(
        workflow_run_id,
        WorkflowRunStatus.FAILED,
        failure_reason=failure_reason,
        failure_message=failure_message,
    )
    await _cascade_cancel_dependents(run.type, project_id, run.revision)


async def _cascade_cancel_dependents(
    workflow_type: WorkflowRunType, project_id: str, revision: int
) -> None:
    """Cancel any active (pending, running, or awaiting approval) run that required-depends on this type."""
    for dependent_type in get_required_dependents(workflow_type):
        dependent_run = await get_project_workflow_run_by_type(
            project_id, dependent_type, revision=revision
        )
        if dependent_run and dependent_run.status in ACTIVE_WORKFLOW_RUN_STATUSES:
            await cancel_workflow_run(str(dependent_run.id), project_id)


def _active_status_priority():
    """RUNNING first, then PENDING, then AWAITING_APPROVAL, then everything else."""
    return case(
        (col(WorkflowRun.status) == WorkflowRunStatus.RUNNING, 0),
        (col(WorkflowRun.status) == WorkflowRunStatus.PENDING, 1),
        (col(WorkflowRun.status) == WorkflowRunStatus.AWAITING_APPROVAL, 2),
        else_=3,
    )


async def get_project_workflow_run_by_type(
    project_id: str,
    type: WorkflowRunType,
    revision: int,
    include_state: bool = False,
) -> Optional[WorkflowRun]:
    """
    Get the most relevant workflow run for a project, type, and revision.

    Priority: RUNNING > PENDING > AWAITING_APPROVAL > latest terminal run.
    This ensures UI shows correct status when multiple runs exist.

    Pass `include_state=True` to undefer `state_json` so the returned run can be
    hydrated via `read_workflow_run_state` after the session closes. Left off by
    default to keep hot status/cancel paths from loading multi-MB payloads.
    """

    async with get_async_db_session() as session:
        # First, try to find an active (running, pending, or awaiting approval) workflow run
        # This is the most common case and avoids loading all historical runs
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
                    col(WorkflowRun.revision) == revision,
                    col(WorkflowRun.status).in_(ACTIVE_WORKFLOW_RUN_STATUSES),
                )
            )
            .order_by(
                _active_status_priority(),
                col(WorkflowRun.created_at).desc(),
            )
            .limit(1)
        )
        if include_state:
            stmt = stmt.options(undefer(col(WorkflowRun.state_json)))  # type: ignore[arg-type]  # SQLModel Mapped[...] is a QueryableAttribute at runtime
        active_run = (await session.execute(stmt)).scalar_one_or_none()

        if active_run:
            return active_run

        # No active run found, get the latest completed run
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
                    col(WorkflowRun.revision) == revision,
                )
            )
            .order_by(col(WorkflowRun.created_at).desc())
            .limit(1)
        )
        if include_state:
            stmt = stmt.options(undefer(col(WorkflowRun.state_json)))  # type: ignore[arg-type]  # SQLModel Mapped[...] is a QueryableAttribute at runtime
        return (await session.execute(stmt)).scalar_one_or_none()


async def get_latest_workflow_run_state_by_type(
    project_id: str,
    type: WorkflowRunType,
    revision: int,
    exclude_run_id: str | None = None,
) -> WorkflowState | None:
    """Hydrated state of the most recent run of this type/revision that has one.

    Used to seed accumulating workflows (e.g. reference_downloader) from the
    prior run's state now that threads are no longer reused. Skips runs that
    never persisted a state: the ``jsonb_typeof(state_json) = 'object'`` filter
    matches only rows holding a real state object, excluding SQL NULL (a
    just-created run leaves state_json unset), JSONB ``null``, and any other
    non-object value. Optionally excludes a specific run. Call this at execution
    time — after the same-type wait resolves — so it reflects the prior run's
    final, not in-flight, state.
    """
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
                    col(WorkflowRun.revision) == revision,
                    func.jsonb_typeof(col(WorkflowRun.state_json)) == "object",
                )
            )
            .order_by(col(WorkflowRun.created_at).desc())
            .limit(1)
            .options(undefer(col(WorkflowRun.state_json)))  # type: ignore[arg-type]  # SQLModel Mapped[...] is a QueryableAttribute at runtime
        )
        if exclude_run_id is not None:
            stmt = stmt.where(col(WorkflowRun.id) != exclude_run_id)
        run = (await session.execute(stmt)).scalar_one_or_none()

    return hydrate_workflow_run_state(run) if run is not None else None


async def get_project_workflow_runs_by_type(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
    include_state: bool = False,
) -> List[WorkflowRun]:
    """
    Get all workflow runs of a specific type for a project and revision.

    Returns all runs ordered by created_at descending (newest first).
    """
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == workflow_type,
                    col(WorkflowRun.revision) == revision,
                )
            )
            .order_by(col(WorkflowRun.created_at).desc())
        )
        if include_state:
            stmt = stmt.options(undefer(col(WorkflowRun.state_json)))  # type: ignore[arg-type]  # SQLModel Mapped[...] is a QueryableAttribute at runtime
        return list((await session.execute(stmt)).scalars().all())


async def get_project_workflow_runs_by_type_with_details(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
) -> List[WorkflowRunDetail]:
    """
    Get all workflow runs of a specific type for a project, including full state.

    Returns all runs ordered by created_at descending (newest first).
    Used for displaying workflow run history in the UI with error status.
    """
    runs = await get_project_workflow_runs_by_type(
        project_id, workflow_type, revision=revision, include_state=True
    )

    # Each run carries its own state_json, so state (and cost) are read per run
    # directly — no checkpointer fan-out, and no thread-sharing band-aid needed.
    hydrated = [hydrate_workflow_run_state_with_status(run) for run in runs]
    states = [state for state, _ in hydrated]
    costs = await asyncio.gather(*[_compute_cost_for_state(s) for s in states])
    return [
        WorkflowRunDetail(run=run, state=state, cost=cost, state_status=status)
        for run, (state, status), cost in zip(runs, hydrated, costs)
    ]


async def get_project_workflow_runs(
    project_id: str,
    revision: int,
    include_internal: bool = False,
) -> List[WorkflowRunDetail]:
    """
    Get the most relevant workflow run for each type in a project revision.

    Returns only 1 row per workflow type, using priority:
    RUNNING > PENDING > AWAITING_APPROVAL > latest terminal run.
    """
    status_priority = _active_status_priority()

    # Use ROW_NUMBER to rank runs within each type
    row_num = func.row_number().over(
        partition_by=col(WorkflowRun.type),
        order_by=[status_priority, col(WorkflowRun.created_at).desc()],
    )

    # Subquery to get ranked runs filtered by revision
    ranked_runs_subquery = (
        select(WorkflowRun, row_num.label("rn"))
        .where(
            and_(
                col(WorkflowRun.project_id) == project_id,
                col(WorkflowRun.revision) == revision,
            )
        )
        .subquery()
    )

    # Select only the top-ranked run for each type (rn = 1)
    stmt = (
        select(WorkflowRun)
        .join(ranked_runs_subquery, col(WorkflowRun.id) == ranked_runs_subquery.c.id)
        .where(
            and_(
                col(WorkflowRun.project_id) == project_id,
                ranked_runs_subquery.c.rn == 1,
            )
        )
        # Load state_json in-session so read_workflow_run_state can hydrate it.
        .options(undefer(col(WorkflowRun.state_json)))  # type: ignore[arg-type]  # SQLModel Mapped[...] is a QueryableAttribute at runtime
    )

    async with get_async_db_session() as session:
        runs = (await session.execute(stmt)).scalars().all()

    # A run whose workflow no longer has a manifest is never surfaced — not even
    # to include_internal=True callers. Both the public share response and the
    # MCP project serializer pass that flag, and neither should hand back a
    # workflow the rest of the API treats as gone. Such a run is also useless as
    # a dependency state: without a manifest it cannot hydrate.
    runs = [run for run in runs if is_available_workflow_type(run.type)]

    # Filter out internal workflows unless explicitly requested
    visible_runs = [
        run for run in runs if include_internal or is_user_visible_workflow(run.type)
    ]

    # Each run carries its own state_json — read state per run directly.
    hydrated = [hydrate_workflow_run_state_with_status(run) for run in visible_runs]
    states = [state for state, _ in hydrated]

    costs = await asyncio.gather(*[_compute_cost_for_state(s) for s in states])
    return [
        WorkflowRunDetail(run=run, state=state, cost=cost, state_status=status)
        for run, (state, status), cost in zip(visible_runs, hydrated, costs)
    ]
