import logging
from typing import List, Optional
from fastapi import HTTPException
from langgraph.types import StateSnapshot
from pydantic import BaseModel

from lib.config.database import get_db
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.nodes.rank_issues import rank_issues
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    ClaimSubstantiatorStateSummary,
    DocumentChunk,
)

logger = logging.getLogger(__name__)


class WorkflowRunDetailed(BaseModel):
    run: WorkflowRun
    state: Optional[ClaimSubstantiatorStateSummary] = None


class UpdateWorkflowRunRequest(BaseModel):
    title: Optional[str] = None


def _convert_state_snapshot(
    state_snapshot: StateSnapshot,
) -> Optional[ClaimSubstantiatorState]:
    try:
        return ClaimSubstantiatorState(**state_snapshot.values)
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


async def get_workflow_run_detailed(id: str, user: User) -> WorkflowRunDetailed:
    with get_db() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == id).first()

    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    if run.user_id is None or run.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    graph = build_claim_substantiator_graph()

    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer)
        state = await app.aget_state(
            {"configurable": {"thread_id": run.langgraph_thread_id}}
        )

    full_state = _convert_state_snapshot(state)

    if full_state is None:
        return WorkflowRunDetailed(run=run, state=None)

    # TODO: temporarily rank issues to be able to display them in the UI - add to graph later
    full_state.ranked_issues = rank_issues(full_state).get("ranked_issues", [])
    summary_state = _convert_to_summary_state(full_state)

    return WorkflowRunDetailed(run=run, state=summary_state)


async def get_workflow_runs(user: User) -> List[WorkflowRun]:
    with get_db() as db:
        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.user_id == user.id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(100)
            .all()
        )

    return runs


async def upsert_workflow_run(
    session_id: str,
    status: WorkflowRunStatus,
    title: Optional[str] = None,
    user: Optional[User] = None,
) -> Optional[str]:
    """
    Create or update a workflow run using the session_id as the key.

    This is the single function for all workflow run database operations.
    It handles both creation (when no run exists) and updates (when it does).

    Args:
        session_id: The LangGraph thread ID (unique identifier)
        status: The workflow status to set
        title: Optional title to set/update
        user: Optional user to assign as owner (only set on creation)

    Returns:
        The workflow run UUID as a string, or None if session_id is not provided
    """
    if not session_id:
        logger.warning("upsert_workflow_run: No session_id provided")
        return None

    with get_db() as db:
        run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.langgraph_thread_id == session_id)
            .first()
        )

        if run is None:
            # Create new run
            run = WorkflowRun(
                langgraph_thread_id=session_id,
                title=title or "Untitled",
                status=status,
                user_id=user.id if user else None,
            )
            db.add(run)
        else:
            # Update existing run
            run.status = status
            if title:
                run.title = title

        db.commit()
        db.refresh(run)
        return str(run.id)


def get_workflow_run_id_by_session(session_id: str) -> Optional[str]:
    """
    Get the workflow run ID for a given session ID.

    Args:
        session_id: The LangGraph thread ID

    Returns:
        The workflow run UUID as a string, or None if not found
    """
    if not session_id:
        return None

    with get_db() as db:
        run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.langgraph_thread_id == session_id)
            .first()
        )
        return str(run.id) if run else None


async def update_workflow_run(
    workflow_run_id: str, request: UpdateWorkflowRunRequest, user: User
) -> WorkflowRun:
    """
    Update a workflow run with the provided fields.

    Args:
        workflow_run_id: The workflow run UUID
        request: UpdateWorkflowRunRequest containing fields to update
        user: The user making the request

    Returns:
        The updated WorkflowRun

    Raises:
        HTTPException: If the workflow run is not found or user doesn't have access
    """
    with get_db() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).first()

        if run is None:
            raise HTTPException(status_code=404, detail="Workflow run not found")

        if run.user_id is None or run.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        if request.title is not None:
            run.title = request.title

        db.commit()
        db.refresh(run)
        return run


async def delete_workflow_run(workflow_run_id: str, user: User) -> None:
    with get_db() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).first()

        if run is None:
            raise HTTPException(status_code=404, detail="Workflow run not found")

        if run.user_id is None or run.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        thread_id = run.langgraph_thread_id

        db.delete(run)
        db.commit()

    try:
        async with get_checkpointer() as checkpointer:
            await checkpointer.adelete_thread(thread_id)
    except Exception as e:
        logger.error(f"Error deleting checkpoints for thread {thread_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error deleting checkpoint data: {str(e)}"
        )


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

    full_state = _convert_state_snapshot(state)
    if full_state is None:
        raise HTTPException(status_code=404, detail="Workflow state not found")

    chunk = next((c for c in full_state.chunks if c.chunk_index == chunk_index), None)
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_index} not found")

    return chunk
