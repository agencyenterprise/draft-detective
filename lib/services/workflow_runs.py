import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from langgraph.types import StateSnapshot
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import is_user_visible_workflow
from lib.workflows.registry import create_graph, get_state_type, get_workflow_manifest
from lib.workflows.workflow_types import WorkflowState

logger = logging.getLogger(__name__)


class WorkflowRunDetail(BaseModel):
    run: WorkflowRun
    state: WorkflowState | None


def _convert_state_snapshot(
    state_snapshot: StateSnapshot,
    state_type: WorkflowState,
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

    return _convert_state_snapshot(state_snapshot, get_state_type(type))


async def get_workflow_run(workflow_run_id: str, user: User = None) -> WorkflowRun:
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
) -> None:
    """Update an existing workflow run's status. Never overwrites CANCELLED."""
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(
            and_(
                col(WorkflowRun.id) == workflow_run_id,
                col(WorkflowRun.status) != WorkflowRunStatus.CANCELLED,
            )
        )
        run = (await session.execute(stmt)).scalar_one_or_none()
        if run:
            now = datetime.utcnow()
            run.status = status
            if status == WorkflowRunStatus.RUNNING and run.started_at is None:
                run.started_at = now
            if status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.CANCELLED):
                run.completed_at = now
            await session.commit()


async def get_workflow_run_status(workflow_run_id: str) -> WorkflowRunStatus | None:
    """Lightweight fetch of just the status for a workflow run. Used for cancellation checks."""
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun.status).where(col(WorkflowRun.id) == workflow_run_id)
        return (await session.execute(stmt)).scalar_one_or_none()


async def cancel_workflow_run(workflow_run_id: str, project_id: str) -> None:
    """
    Cancel a workflow run and recursively cancel any active runs that depend on it.

    Only cascades through required_dependencies — optional dependents are left running
    since they handle missing data by design.
    """
    from lib.services.workflow_progress import cancel_workflow_progress
    from lib.workflows.dependency_resolver import get_required_dependents

    run = await get_workflow_run(workflow_run_id)
    await cancel_workflow_progress(run.project_id, run.type)
    await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.CANCELLED)

    for dependent_type in get_required_dependents(run.type):
        dependent_run = await get_project_workflow_run_by_type(
            project_id, dependent_type, revision=run.revision
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
            select(WorkflowRun.id)
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
    project_id: str, workflow_type: WorkflowRunType, revision: int,
) -> List[WorkflowRunDetail]:
    """
    Get all workflow runs of a specific type for a project, including full state.

    Returns all runs ordered by created_at descending (newest first).
    Used for displaying workflow run history in the UI with error status.
    """
    runs = await get_project_workflow_runs_by_type(project_id, workflow_type, revision=revision)

    # Fetch all workflow states in parallel to avoid N+1 query pattern
    states = await asyncio.gather(
        *[
            get_workflow_run_state_by_thread_id(run.langgraph_thread_id, run.type)
            for run in runs
        ]
    )

    return [WorkflowRunDetail(run=run, state=state) for run, state in zip(runs, states)]


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

    return [
        WorkflowRunDetail(run=run, state=state)
        for run, state in zip(visible_runs, states)
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
