"""
Public API routes for unauthenticated access to shared resources.

These routes require a valid share token instead of authentication.
"""

from fastapi import APIRouter, HTTPException

from lib.services.projects.overview import ProjectOverview, get_project_overview
from lib.services.projects.service import get_project_access
from lib.services.projects.share_links import get_resource_by_token

router = APIRouter(prefix="/api/public", tags=["public"])


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

    # No user on purpose: a share page renders what any holder of the link
    # sees, so an owner previewing their own link gets READ like everyone else.
    project, access_level = await get_project_access(
        str(share_link.project_id), user=None, share_token=token
    )
    return await get_project_overview(project, access_level)
