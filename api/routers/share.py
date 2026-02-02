"""
API routes for managing share links (authenticated).

These routes require authentication and allow users to manage sharing
for their own resources.
"""

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from lib.models.user import User
from lib.services.projects import get_user_project
from lib.services.share_links import (
    ShareStatusResponse,
    disable_sharing,
    enable_sharing,
    get_share_status,
)

router = APIRouter(tags=["share"])


@router.get("/api/projects/{project_id}/share", response_model=ShareStatusResponse)
async def get_project_share_status(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the sharing status for a project."""
    project = await get_user_project(project_id, current_user)
    return await get_share_status("project", project.id)


@router.post(
    "/api/projects/{project_id}/share/enable", response_model=ShareStatusResponse
)
async def enable_project_sharing(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Enable sharing for a project (creates a share link if none exists)."""
    project = await get_user_project(project_id, current_user)
    return await enable_sharing("project", project.id, current_user)


@router.post(
    "/api/projects/{project_id}/share/disable", response_model=ShareStatusResponse
)
async def disable_project_sharing(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Disable sharing for a project (deactivates the share link)."""
    project = await get_user_project(project_id, current_user)
    return await disable_sharing("project", project.id)
