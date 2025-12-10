"""
Public API routes for unauthenticated access to shared resources.

These routes require a valid share token instead of authentication.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.config.database import get_db
from lib.models.project import Project
from lib.services.share_links import get_resource_by_token
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorStateSummary
from lib.workflows.models import WorkflowRunType

router = APIRouter(prefix="/api/public", tags=["public"])


class SharedProjectInfo(BaseModel):
    """Minimal project info for shared view (no sensitive data)."""

    id: str
    title: str
    created_at: datetime


class SharedWorkflowRun(BaseModel):
    """Minimal workflow run info for shared view."""

    id: str
    type: str
    status: str


class SharedProjectResponse(BaseModel):
    """Response for a shared project with all necessary data."""

    project: SharedProjectInfo
    workflow_run: Optional[SharedWorkflowRun] = None
    state: Optional[ClaimSubstantiatorStateSummary] = None


@router.get("/share/{token}", response_model=SharedProjectResponse)
async def get_shared_resource(token: str):
    """
    Access a shared resource by token.

    This endpoint does not require authentication - the token IS the auth.
    Returns project info and workflow state in a single call.
    """
    share_link = await get_resource_by_token(token)
    if not share_link:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    if share_link.resource_type != "project":
        raise HTTPException(status_code=400, detail="Unsupported resource type")

    with get_db() as db:
        project = db.query(Project).filter(Project.id == share_link.resource_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    workflow_run = await get_project_workflow_run_by_type(
        str(project.id), WorkflowRunType.CLAIM_SUBSTANTIATION
    )

    workflow_run_info = None
    state = None

    if workflow_run:
        workflow_run_info = SharedWorkflowRun(
            id=str(workflow_run.id),
            type=str(workflow_run.type),  # stored as string in DB
            status=workflow_run.status.value,
        )
        state = await get_workflow_run_state_by_thread_id(
            workflow_run.langgraph_thread_id, WorkflowRunType.CLAIM_SUBSTANTIATION
        )

    return SharedProjectResponse(
        project=SharedProjectInfo(
            id=str(project.id),
            title=project.title,
            created_at=project.created_at,
        ),
        workflow_run=workflow_run_info,
        state=state,
    )
