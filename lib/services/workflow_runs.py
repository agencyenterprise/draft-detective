import logging
from typing import List, Optional

from fastapi import HTTPException
from langgraph.types import StateSnapshot
from sqlalchemy import select
from sqlmodel import and_

from lib.config.database import get_db
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.nodes.rank_issues import rank_issues
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    ClaimSubstantiatorStateSummary,
    DocumentChunk,
)
from lib.workflows.registry import WorkflowState, create_graph, get_state_type

logger = logging.getLogger(__name__)


def _convert_state_snapshot(
    state_snapshot: StateSnapshot,
    state_type: WorkflowState,
) -> Optional[WorkflowState]:
    try:
        return state_type(**state_snapshot.values)
    except Exception as e:
        logger.warning(
            f"Error converting state snapshot for thread {state_snapshot.config['configurable']['thread_id']} (possibly an old state schema version): {e}"
        )
        return None


def _convert_to_summary_state(
    full_state: ClaimSubstantiatorState,
) -> ClaimSubstantiatorStateSummary:
    """Convert full state to summary state with lightweight chunks"""
    return ClaimSubstantiatorStateSummary(
        **full_state.model_dump(exclude={"chunks"}),
        chunks=[chunk.to_summary() for chunk in full_state.chunks],
    )


async def get_workflow_run_state_by_thread_id(
    thread_id: str, type: WorkflowRunType
) -> WorkflowState:
    async with get_checkpointer() as checkpointer:
        graph = create_graph(type)
        app = graph.compile(checkpointer=checkpointer)
        state_snapshot = await app.aget_state(
            {"configurable": {"thread_id": thread_id}}
        )

    state = _convert_state_snapshot(state_snapshot, get_state_type(type, summary=False))

    if type == WorkflowRunType.CLAIM_SUBSTANTIATION:
        # TODO: temporarily rank issues to be able to display them in the UI - add to graph later
        state.ranked_issues = rank_issues(state).get("ranked_issues", [])
        state = _convert_to_summary_state(state)

    return state


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
    workflow_run_id: str, user: User = None
) -> WorkflowState:
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


async def get_project_workflow_runs(project_id: str) -> List[WorkflowRun]:
    with get_db() as db:
        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.project_id == project_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(100)
            .all()
        )

    return runs


async def get_chunk_details(workflow_run_id: str, chunk_index: int) -> DocumentChunk:
    """
    Get detailed analysis for a specific chunk.
    Returns the full chunk with all analysis (used for lazy loading chunk details).
    """
    with get_db() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).first()

    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    graph = build_claim_substantiator_graph()
    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer)
        state = await app.aget_state(
            {"configurable": {"thread_id": run.langgraph_thread_id}}
        )

    full_state = _convert_state_snapshot(state, ClaimSubstantiatorState)
    if full_state is None:
        raise HTTPException(status_code=404, detail="Workflow state not found")

    chunk = next((c for c in full_state.chunks if c.chunk_index == chunk_index), None)
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_index} not found")

    return chunk
