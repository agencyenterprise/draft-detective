import logging
import uuid
from typing import List, Optional

from fastapi import HTTPException
from langgraph.types import StateSnapshot
from pydantic import BaseModel
from sqlalchemy import select
from sqlmodel import and_

from lib.config.database import get_db
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import is_user_visible_workflow
from lib.workflows.registry import create_graph, get_state_type
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
        result = db.execute(
            select(WorkflowRun, Project)
            .outerjoin(Project)
            .filter(WorkflowRun.id == workflow_run_id)
        ).one()

    if result is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    run, project = result

    if user is not None and project is not None and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return run


async def get_workflow_run_state(
    workflow_run_id: str, user: User | None = None
) -> WorkflowState | None:
    run = await get_workflow_run(workflow_run_id, user)
    return await get_workflow_run_state_by_thread_id(run.langgraph_thread_id, run.type)


async def upsert_workflow_run(
    thread_id: str,
    project_id: str,
    status: WorkflowRunStatus,
    type: WorkflowRunType,
) -> str:
    """Create or update a workflow run using the thread_id as the key."""

    with get_db() as db:
        run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.langgraph_thread_id == thread_id)
            .first()
        )

        if run is None:
            # Create new run
            run = WorkflowRun(
                langgraph_thread_id=thread_id,
                project_id=project_id,
                status=status,
                type=type,
            )
            db.add(run)
        else:
            # Update existing run
            run.status = status

        db.commit()
        db.refresh(run)
    return str(run.id)


async def get_project_workflow_run_by_type(
    project_id: str, type: WorkflowRunType
) -> Optional[WorkflowRun]:
    with get_db() as db:
        run = (
            db.query(WorkflowRun)
            .filter(
                and_(WorkflowRun.project_id == project_id, WorkflowRun.type == type)
            )
            .order_by(WorkflowRun.created_at.desc())
            .first()
        )
        return run


async def get_project_workflow_runs(
    project_id: str, include_internal: bool = False
) -> List[WorkflowRunDetail]:
    """
    Get workflow runs for a project.

    Args:
        project_id: The project ID
        include_internal: If True, include internal workflows (for dependency resolution)

    Returns:
        List of workflow run details
    """
    with get_db() as db:
        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.project_id == project_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(100)
            .all()
        )

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
    """Get the thread ID for a workflow run, or create a new one if it doesn't exist."""

    if workflow_run is not None:
        return workflow_run.langgraph_thread_id
    else:
        return str(uuid.uuid4())
