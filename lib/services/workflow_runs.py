import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Type, cast

from fastapi import HTTPException
from langgraph.types import StateSnapshot
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import (
    TERMINAL_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_cost.breakdown import CostBreakdown
from lib.services.workflow_cost.extractor import walk_state_for_usage
from lib.services.workflow_cost.pricing import compute_cost
from lib.services.workflow_progress import cancel_workflow_progress
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.dependency_resolver import get_required_dependents
from lib.workflows.models import is_user_visible_workflow
from lib.workflows.registry import create_graph, get_state_type, get_workflow_manifest
from lib.workflows.workflow_types import WorkflowState

logger = logging.getLogger(__name__)


class WorkflowRunDetail(BaseModel):
    run: WorkflowRun
    state: WorkflowState | None
    cost: CostBreakdown | None = None


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


def _canonical_run_ids_per_thread(runs: List[WorkflowRun]) -> set[uuid.UUID]:
    """Return the set of run IDs that are the most recent owners of their thread_id.

    Multiple WorkflowRun rows can share a langgraph_thread_id (re-runs reuse threads),
    so older runs see the latest run's state from the checkpointer — their cost would
    be misleading. Only attribute cost to the latest run per thread.
    """
    latest: dict[str, WorkflowRun] = {}
    for run in runs:
        existing = latest.get(run.langgraph_thread_id)
        if existing is None or run.created_at > existing.created_at:
            latest[run.langgraph_thread_id] = run
    return {r.id for r in latest.values()}


def _convert_state_snapshot(
    state_snapshot: StateSnapshot,
    state_type: Type[WorkflowState],
) -> WorkflowState | None:
    if not state_snapshot or not state_snapshot.values:
        return None

    try:
        return state_type(**state_snapshot.values)
    except Exception as e:
        logger.warning(
            f"Error converting state snapshot for thread {state_snapshot.config['configurable']['thread_id']} (possibly an old state schema version): {e}"
        )
        return None


async def get_workflow_run_state_by_thread_id(
    thread_id: str, type: WorkflowRunType
) -> WorkflowState | None:
    manifest = get_workflow_manifest(type, raise_exception=False)
    if manifest is None:
        return None

    async with get_checkpointer() as checkpointer:
        graph = create_graph(type)
        app = graph.compile(checkpointer=checkpointer)
        try:
            state_snapshot = await app.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
        except Exception as e:
            logger.error(
                f"Error getting state snapshot for thread {thread_id}: {e}",
                exc_info=True,
            )
            return None

    return _convert_state_snapshot(
        state_snapshot, cast(Type[WorkflowState], get_state_type(type))
    )


async def get_workflow_run(
    workflow_run_id: str, user: Optional[User] = None
) -> WorkflowRun:
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun, Project)
            .outerjoin(Project)
            .where(col(WorkflowRun.id) == workflow_run_id)
        )
        result = (await session.execute(stmt)).one_or_none()

    if result is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    run, project = result.tuple()

    if user is not None and project is not None and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return run


async def get_workflow_run_state(
    workflow_run_id: str, user: User | None = None
) -> WorkflowState | None:
    run = await get_workflow_run(workflow_run_id, user)
    return await get_workflow_run_state_by_thread_id(run.langgraph_thread_id, run.type)


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
    """Cancel any PENDING/RUNNING workflow runs that required-depend on this type."""
    for dependent_type in get_required_dependents(workflow_type):
        dependent_run = await get_project_workflow_run_by_type(
            project_id, dependent_type, revision=revision
        )
        if dependent_run and dependent_run.status in (
            WorkflowRunStatus.PENDING,
            WorkflowRunStatus.RUNNING,
        ):
            await cancel_workflow_run(str(dependent_run.id), project_id)


async def get_project_workflow_run_by_type(
    project_id: str,
    type: WorkflowRunType,
    revision: int,
) -> Optional[WorkflowRun]:
    """
    Get the most relevant workflow run for a project, type, and revision.

    Priority: RUNNING > PENDING > latest COMPLETED
    This ensures UI shows correct status when multiple runs exist.
    """

    async with get_async_db_session() as session:
        # First, try to find an active (RUNNING or PENDING) workflow run
        # This is the most common case and avoids loading all historical runs
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
                    col(WorkflowRun.revision) == revision,
                    col(WorkflowRun.status).in_(
                        [WorkflowRunStatus.RUNNING, WorkflowRunStatus.PENDING]
                    ),
                )
            )
            .order_by(
                # RUNNING takes priority over PENDING
                (col(WorkflowRun.status) == WorkflowRunStatus.RUNNING).desc(),
                col(WorkflowRun.created_at).desc(),
            )
            .limit(1)
        )
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
        return (await session.execute(stmt)).scalar_one_or_none()


async def has_completed_workflow_run_any_revision(
    project_id: str,
    type: WorkflowRunType,
) -> bool:
    """Return True if any COMPLETED run of this type exists for the project, across all revisions."""
    async with get_async_db_session() as session:
        stmt = (
            select(col(WorkflowRun.id))
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
                    col(WorkflowRun.status) == WorkflowRunStatus.COMPLETED,
                )
            )
            .limit(1)
        )
        return (await session.execute(stmt)).first() is not None


async def get_project_workflow_runs_by_type(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
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
        project_id, workflow_type, revision=revision
    )

    # Fetch all workflow states in parallel to avoid N+1 query pattern
    states = await asyncio.gather(
        *[
            get_workflow_run_state_by_thread_id(run.langgraph_thread_id, run.type)
            for run in runs
        ]
    )

    canonical_ids = _canonical_run_ids_per_thread(list(runs))
    cost_states = [s if r.id in canonical_ids else None for r, s in zip(runs, states)]
    costs = await asyncio.gather(*[_compute_cost_for_state(s) for s in cost_states])
    return [
        WorkflowRunDetail(run=run, state=state, cost=cost)
        for run, state, cost in zip(runs, states, costs)
    ]


async def get_project_workflow_runs(
    project_id: str,
    revision: int,
    include_internal: bool = False,
) -> List[WorkflowRunDetail]:
    """
    Get the most relevant workflow run for each type in a project revision.

    Returns only 1 row per workflow type, using priority: RUNNING > PENDING > latest COMPLETED.
    """
    # Build priority ordering: RUNNING (0) > PENDING (1) > others (2)
    status_priority = case(
        (col(WorkflowRun.status) == WorkflowRunStatus.RUNNING, 0),
        (col(WorkflowRun.status) == WorkflowRunStatus.PENDING, 1),
        else_=2,
    )

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
    )

    async with get_async_db_session() as session:
        runs = (await session.execute(stmt)).scalars().all()

    # Filter out internal workflows unless explicitly requested
    visible_runs = [
        run for run in runs if include_internal or is_user_visible_workflow(run.type)
    ]

    # Fetch all workflow states in parallel to avoid N+1 query pattern
    states = await asyncio.gather(
        *[
            get_workflow_run_state_by_thread_id(run.langgraph_thread_id, run.type)
            for run in visible_runs
        ]
    )

    costs = await asyncio.gather(*[_compute_cost_for_state(s) for s in states])
    return [
        WorkflowRunDetail(run=run, state=state, cost=cost)
        for run, state, cost in zip(visible_runs, states, costs)
    ]


def get_thread_id_for_workflow_run(workflow_run: WorkflowRun | None) -> str:
    """
    Get the thread ID for a workflow run, or create a new one if it doesn't exist.

    Thread IDs are reused across workflow runs of the same type for a project to maintain
    LangGraph checkpoint continuity. This allows subsequent runs to resume from previously
    computed state (e.g., already-processed document chunks) rather than starting fresh.

    Args:
        workflow_run: An existing workflow run to get the thread_id from, or None for new projects

    Returns:
        The existing thread_id if a run exists, otherwise a new UUID
    """
    if workflow_run is not None:
        return workflow_run.langgraph_thread_id
    return str(uuid.uuid4())
