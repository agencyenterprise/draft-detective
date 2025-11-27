from fastapi import APIRouter, Depends

from api.auth import get_current_user
from lib.models.project import Project
from lib.models.user import User
from lib.services.projects import (
    ProjectDetailed,
    ProjectListItem,
    UpdateProjectRequest,
    delete_project,
    get_user_project_detailed,
    get_user_projects,
    update_user_project,
)

router = APIRouter(tags=["projects"])


@router.get("/api/projects", response_model=list[ProjectListItem])
async def list_projects_endpoint(current_user: User = Depends(get_current_user)):
    """List all projects for the current user"""

    return await get_user_projects(user=current_user)


@router.get("/api/project/{project_id}", response_model=ProjectDetailed)
async def get_project_endpoint(
    project_id: str, current_user: User = Depends(get_current_user)
):
    """Get a project by ID"""

    return await get_user_project_detailed(project_id, user=current_user)


@router.patch("/api/project/{project_id}", response_model=Project)
async def update_project_endpoint(
    project_id: str,
    request: UpdateProjectRequest,
    current_user: User = Depends(get_current_user),
):
    """Update a project with the provided fields"""
    return await update_user_project(project_id, request, user=current_user)


@router.delete("/api/project/{project_id}")
async def delete_project_endpoint(
    project_id: str, current_user: User = Depends(get_current_user)
):
    """Delete a project and all associated results"""

    await delete_project(project_id, user=current_user)

    return {"message": "Project deleted successfully", "id": project_id}
