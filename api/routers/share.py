"""
API routes for managing share links (authenticated).

These routes require authentication and allow users to manage sharing
for their own resources.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlmodel import col

from api.auth import get_current_user
from lib.config.database import get_db
from lib.models.project import Project
from lib.models.user import User
from lib.services.share_links import (
    ShareStatusResponse,
    disable_sharing,
    enable_sharing,
    get_share_status,
)

router = APIRouter(tags=["share"])


def _verify_project_ownership(project_id: str, user: User) -> uuid.UUID:
    """Verify user owns the project and return the project UUID."""
    with get_db() as db:
        stmt = select(Project).where(col(Project.id) == project_id)
        project = db.execute(stmt).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return uuid.UUID(project_id)


@router.get("/api/projects/{project_id}/share", response_model=ShareStatusResponse)
async def get_project_share_status(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the sharing status for a project."""
    project_uuid = _verify_project_ownership(project_id, current_user)
    return await get_share_status("project", project_uuid)


@router.post(
    "/api/projects/{project_id}/share/enable", response_model=ShareStatusResponse
)
async def enable_project_sharing(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Enable sharing for a project (creates a share link if none exists)."""
    project_uuid = _verify_project_ownership(project_id, current_user)
    return await enable_sharing("project", project_uuid, current_user)


@router.post(
    "/api/projects/{project_id}/share/disable", response_model=ShareStatusResponse
)
async def disable_project_sharing(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Disable sharing for a project (deactivates the share link)."""
    project_uuid = _verify_project_ownership(project_id, current_user)
    return await disable_sharing("project", project_uuid)
