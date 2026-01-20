import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi import File as FastAPIUploadFile
from fastapi import Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse

from api.auth import get_current_user, get_current_user_optional
from api.models import WorkflowProgressResponse
from api.upload import save_uploaded_files_to_db
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User
from lib.services.docx_workflow_service import get_or_generate_docx
from lib.services.files import create_project_files_zip
from lib.services.projects import (
    ProjectDetailed,
    ProjectListItem,
    UpdateProjectRequest,
    create_project,
    delete_project,
    get_project_files,
    get_shared_project_detailed,
    get_user_project_detailed,
    get_user_projects,
    update_user_project,
)
from lib.services.share_links import get_resource_by_token
from lib.services.workflow_progress import get_project_workflow_progress

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
    project_id: str,
    include_internal: bool = False,
    current_user: User = Depends(get_current_user),
):
    """Get a project by ID. Set include_internal=true to see internal workflows."""
    return await get_user_project_detailed(
        project_id, user=current_user, include_internal=include_internal
    )


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
    share_token: Optional[str] = Query(
        default=None,
        description="Share token to include share links in comments",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Download DOCX with AI comments.

    Uses cached version if available, otherwise generates via workflow.
    First request may take a few seconds as it generates the DOCX.
    Subsequent requests with the same share_token (or none) are instant.
    """

    await check_project_access(project_id, current_user, share_token)

    try:
        # Get cached or generate DOCX via workflow (with caching)
        file_path, filename = await get_or_generate_docx(
            project_id=project_id,
            share_token=share_token,
            use_cache=True,
        )
    except Exception as e:
        logger.error("Failed to generate DOCX: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate DOCX: {str(e)}",
        )

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.get("/api/project/{project_id}/files", response_model=List[File])
async def list_project_files_endpoint(
    project_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token for shared projects. If not provided, the current user must be the owner of the project.",
    ),
):
    """Get all files for a project"""

    await check_project_access(project_id, current_user, share_token)
    return await get_project_files(project_id)


@router.get("/api/project/{project_id}/files/download-all")
async def download_all_project_files(
    project_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token for shared projects. If not provided, the current user must be the owner of the project.",
    ),
    roles: Optional[List[FileRole]] = Query(
        default=[FileRole.MAIN, FileRole.SUPPORT],
        description="Filter files by role(s). If not provided, main and support files are included by default.",
    ),
):
    """Download all project files as a ZIP archive"""

    # Verify project access
    project_detail = await check_project_access(project_id, current_user, share_token)

    # Create zip file using service
    zip_buffer, _ = await create_project_files_zip(project_id, roles=roles)

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


@router.get(
    "/api/project/{project_id}/workflow-progress",
    response_model=List[WorkflowProgressResponse],
)
async def get_project_workflow_progress_endpoint(
    project_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token for shared projects.",
    ),
):
    """Get all workflow progress entries for a project."""

    project_detail = await check_project_access(project_id, current_user, share_token)
    progress_list = get_project_workflow_progress(project_detail.project.id)
    return [WorkflowProgressResponse.model_validate(p) for p in progress_list]


async def check_project_access(
    project_id: str,
    current_user: Optional[User] = None,
    share_token: Optional[str] = None,
) -> ProjectDetailed:
    """Check if a user or share token gives access to a project. Raises HTTPException if access is denied. Returns the project detailed if access is granted."""

    if share_token:
        share_link = await get_resource_by_token(share_token)
        if share_link is None or str(share_link.resource_id) != project_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return await get_shared_project_detailed(str(share_link.resource_id))
    elif current_user is not None:
        return await get_user_project_detailed(project_id, user=current_user)
    else:
        raise HTTPException(status_code=403, detail="Access denied")
