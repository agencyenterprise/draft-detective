import logging
import uuid
from typing import List, Optional

from fastapi import HTTPException
from langgraph.types import StateSnapshot
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlmodel import and_, col

from lib.config.database import get_db
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import is_user_visible_workflow
from lib.workflows.registry import create_graph, get_state_type, get_workflow_manifest
from lib.workflows.types import WorkflowState

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
    with get_db() as db:
        stmt = (
            select(WorkflowRun, Project)
            .outerjoin(Project)
            .where(col(WorkflowRun.id) == workflow_run_id)
        )
        result = db.execute(stmt).one_or_none()

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
) -> str:
    """Create a new workflow run record."""
    with get_db() as db:
        run = WorkflowRun(
            langgraph_thread_id=thread_id,
            project_id=project_id,
            status=status,
            type=type,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
    return str(run.id)


async def update_workflow_run_status(
    workflow_run_id: str,
    status: WorkflowRunStatus,
) -> None:
    """Update an existing workflow run's status."""
    with get_db() as db:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == workflow_run_id)
        run = db.execute(stmt).scalar_one_or_none()
        if run:
            run.status = status
            db.commit()


async def get_project_workflow_run_by_type(
    project_id: str, type: WorkflowRunType
) -> Optional[WorkflowRun]:
    """
    Get the most relevant workflow run for a project and type.

    Priority: RUNNING > PENDING > latest COMPLETED
    This ensures UI shows correct status when multiple runs exist.
    """
    with get_db() as db:
        # First, try to find an active (RUNNING or PENDING) workflow run
        # This is the most common case and avoids loading all historical runs
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
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
        active_run = db.execute(stmt).scalar_one_or_none()

        if active_run:
            return active_run

        # No active run found, get the latest completed run
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.type) == type,
                )
            )
            .order_by(col(WorkflowRun.created_at).desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()


async def get_project_workflow_runs(
    project_id: str, include_internal: bool = False
) -> List[WorkflowRunDetail]:
    """
    Get the most relevant workflow run for each type in a project.

    Returns only 1 row per workflow type, using priority: RUNNING > PENDING > latest COMPLETED.

    Args:
        project_id: The project ID
        include_internal: If True, include internal workflows (for dependency resolution)

    Returns:
        List of workflow run details (one per workflow type)
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

    # Subquery to get ranked runs
    ranked_runs_subquery = (
        select(WorkflowRun, row_num.label("rn"))
        .where(col(WorkflowRun.project_id) == project_id)
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

    with get_db() as db:
        runs = db.execute(stmt).scalars().all()

    details = []
    for run in runs:
        # Filter out internal workflows unless explicitly requested
        if not include_internal and not is_user_visible_workflow(run.type):
            continue

        state = await get_workflow_run_state_by_thread_id(
            run.langgraph_thread_id, run.type
        )
        details.append(WorkflowRunDetail(run=run, state=state))

    return details


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
