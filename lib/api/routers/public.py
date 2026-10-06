"""
Public API routes for unauthenticated access to shared resources.

These routes require a valid share token instead of authentication.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.services.project_overview import ProjectOverview, get_project_overview
from lib.services.projects import get_project_access
from lib.services.share_links import get_resource_by_token

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


@router.get("/share/{token}", response_model=ProjectOverview)
async def get_shared_resource(token: str):
    """
    Access a shared resource by token.

    This endpoint does not require authentication - the token IS the auth.
    The share page knows only the token, so this resolves it to its project
    and returns the same overview as `/api/project/{id}/overview?share_token=`.
    The heavier parts come from the project routes with `share_token`.
    """
    share_link = await get_resource_by_token(token)
    if not share_link:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    if share_link.resource_type != "project":
        raise HTTPException(status_code=400, detail="Unsupported resource type")

    # No user on purpose: a share page renders what any holder of the link
    # sees, so an owner previewing their own link gets READ like everyone else.
    project, access_level = await get_project_access(
        str(share_link.resource_id), user=None, share_token=token
    )
    return await get_project_overview(project, access_level)
