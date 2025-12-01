import os

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from api.auth import get_current_user
from lib.config.database import get_db
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.docx_manipulator import docx_manipulator_service
from lib.services.projects import (
    ProjectDetailed,
    ProjectListItem,
    UpdateProjectRequest,
    delete_project,
    get_user_project_detailed,
    get_user_projects,
    update_user_project,
)
from lib.services.workflow_runs import get_workflow_run_detailed

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


@router.get("/api/projects/{project_id}/docx/download")
async def download_project_docx(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download DOCX file for project - reviewed version if available, otherwise original"""

    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.user_id is None or project.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        workflow_run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.project_id == project_id)
            .order_by(WorkflowRun.created_at.desc())
            .first()
        )

        if workflow_run is None:
            raise HTTPException(
                status_code=404,
                detail="No workflow run found for this project",
            )

    workflow_detailed = await get_workflow_run_detailed(
        str(workflow_run.id), user=current_user
    )

    if not workflow_detailed.state or not workflow_detailed.state.file:
        raise HTTPException(status_code=404, detail="Workflow state not found")

    original_file_path = workflow_detailed.state.file.original_file_path
    if not original_file_path or not original_file_path.endswith(".docx"):
        raise HTTPException(
            status_code=404,
            detail="No DOCX file available for this project",
        )

    # Try to get reviewed version first
    reviewed_path = docx_manipulator_service.get_output_path(str(workflow_run.id))
    if reviewed_path.exists():
        file_path = str(reviewed_path)
        is_reviewed = True
    else:
        # Fall back to original
        file_path = original_file_path
        is_reviewed = False

    base_name, _ = os.path.splitext(workflow_detailed.state.file.file_name)
    filename = f"{base_name}_reviewed.docx" if is_reviewed else f"{base_name}.docx"

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
