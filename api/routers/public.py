"""
Public API routes for unauthenticated access to shared resources.

These routes require a valid share token instead of authentication.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.services.projects import ProjectDetailed, get_user_project_detailed
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


@router.get("/share/{token}", response_model=ProjectDetailed)
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

    return await get_user_project_detailed(share_link.resource_id, user=None)
