import io
import logging
import os
from typing import List

from fastapi import APIRouter, Depends
from fastapi import File as FastAPIUploadFile
from fastapi import Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse

from api.auth import get_current_user
from api.upload import save_uploaded_files_to_db
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User
from lib.services.docx_manipulator import docx_manipulator_service
from lib.services.files import create_project_files_zip
from lib.services.projects import (
    ProjectDetailed,
    ProjectListItem,
    UpdateProjectRequest,
    create_project,
    delete_project,
    get_user_project_detailed,
    get_user_project_files,
    get_user_projects,
    update_user_project,
)
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorStateSummary
from lib.workflows.models import WorkflowRunType

router = APIRouter(tags=["projects"])
logger = logging.getLogger(__name__)


@router.post(
    "/api/projects", response_model=ProjectDetailed, status_code=status.HTTP_201_CREATED
)
async def create_project_endpoint(
    title: str = Form(...),
    main_document: UploadFile = FastAPIUploadFile(...),
    current_user: User = Depends(get_current_user),
):
    """Create a project with a main document."""

    project: Project | None = None
    try:
        project = await create_project(title=title, user=current_user)

        await save_uploaded_files_to_db(
            uploaded_files=[main_document],
            project_id=project.id,
            user_id=current_user.id,
            roles=[FileRole.MAIN],
            description="The main document under analysis",
        )

        return ProjectDetailed(project=project, workflow_runs=[])
    except Exception as e:
        logger.error("Failed to create project: %s", e, exc_info=True)

        if project is not None:
            try:
                await delete_project(str(project.id), user=current_user)
            except Exception as cleanup_error:  # pragma: no cover - best effort cleanup
                logger.error(
                    "Failed to clean up project %s after creation error: %s",
                    project.id,
                    cleanup_error,
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )


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

    project_detail = await get_user_project_detailed(project_id, user=current_user)

    claim_substantiation_workflow_run = await get_project_workflow_run_by_type(
        project_detail.project.id, WorkflowRunType.CLAIM_SUBSTANTIATION
    )
    if not claim_substantiation_workflow_run:
        raise HTTPException(
            status_code=404, detail="Claim substantiation workflow run not found"
        )

    claim_substantiation_state: ClaimSubstantiatorStateSummary = (
        await get_workflow_run_state_by_thread_id(
            claim_substantiation_workflow_run.langgraph_thread_id,
            claim_substantiation_workflow_run.type,
        )
    )

    if not claim_substantiation_state or not claim_substantiation_state.file:
        raise HTTPException(status_code=404, detail="Workflow state not found")

    original_file_path = claim_substantiation_state.file.original_file_path
    if not original_file_path or not original_file_path.endswith(".docx"):
        raise HTTPException(
            status_code=404,
            detail="No DOCX file available for this project",
        )

    # Try to get reviewed version first
    reviewed_path = docx_manipulator_service.get_output_path(
        str(claim_substantiation_workflow_run.id)
    )
    if reviewed_path.exists():
        file_path = str(reviewed_path)
        is_reviewed = True
    else:
        # Fall back to original
        file_path = original_file_path
        is_reviewed = False

    base_name, _ = os.path.splitext(claim_substantiation_state.file.file_name)
    filename = f"{base_name}_reviewed.docx" if is_reviewed else f"{base_name}.docx"

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.get("/api/project/{project_id}/files", response_model=List[File])
async def list_project_files_endpoint(
    project_id: str, current_user: User = Depends(get_current_user)
):
    """Get all files for a project"""

    return await get_user_project_files(project_id, user=current_user)


@router.get("/api/project/{project_id}/files/download-all")
async def download_all_project_files(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download all project files as a ZIP archive"""

    # Verify project access
    project_detail = await get_user_project_detailed(project_id, user=current_user)

    # Create zip file using service
    zip_buffer, _ = await create_project_files_zip(project_id)

    # Generate filename from project title
    project_title = project_detail.project.title or "project"

    # Sanitize filename (remove invalid characters)
    safe_title = "".join(
        c for c in project_title if c.isalnum() or c in (" ", "-", "_")
    ).strip()

    if not safe_title:
        safe_title = "project"

    zip_filename = f"{safe_title}_files.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
