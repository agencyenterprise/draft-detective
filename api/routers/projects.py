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
from lib.services.files import create_project_files_zip, delete_project_files
from lib.services.projects import (
    ProjectDetailed,
    ProjectListItem,
    UpdateProjectRequest,
    create_project,
    delete_project,
    get_project_detailed_from_project,
    get_project_files,
    get_shared_project,
    get_user_project,
    get_user_projects,
    update_user_project,
)
from lib.services.references import add_file_to_reference, remove_file_from_references
from lib.services.share_links import get_resource_by_token
from lib.services.workflow_progress import get_project_workflow_progress
from lib.services.workflow_runs import (
    WorkflowRunDetail,
    get_project_workflow_runs_by_type_with_details,
)
from lib.models.workflow_run import WorkflowRunType
from lib.workflows.models import SeverityEnum
from api.models import CreateProjectRequest

router = APIRouter(tags=["projects"])
logger = logging.getLogger(__name__)


@router.post(
    "/api/projects", response_model=ProjectDetailed, status_code=status.HTTP_201_CREATED
)
async def create_project_endpoint(
    request: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a project.

    This endpoint creates the project first, then files are uploaded
    separately via the /api/upload endpoints.
    """
    try:
        project = await create_project(title=request.title, user=current_user)
        return ProjectDetailed(project=project, workflow_runs=[])
    except Exception as e:
        logger.error("Failed to create project: %s", e, exc_info=True)
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
    share_token: Optional[str] = Query(
        default=None,
        description="Share token to get project details",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a project by ID. Set include_internal=true to see internal workflows."""

    project = await check_project_access(project_id, current_user, share_token)
    project_detailed = await get_project_detailed_from_project(
        project, include_internal=include_internal
    )
    return project_detailed


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
    severities: Optional[List[SeverityEnum]] = Query(
        default=None,
        description="Filter issues by severity levels",
    ),
    workflow_types: Optional[List[WorkflowRunType]] = Query(
        default=None,
        description="Filter issues by workflow types",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Download DOCX with AI comments.

    Uses cached version if available, otherwise generates via workflow.
    First request may take a few seconds as it generates the DOCX.
    Subsequent requests with the same share_token, severities, and workflow_types filters are instant.
    """

    await check_project_access(project_id, current_user, share_token)

    try:
        # Get cached or generate DOCX via workflow (with caching)
        file_path, filename = await get_or_generate_docx(
            project_id=project_id,
            share_token=share_token,
            severities=severities,
            workflow_types=workflow_types,
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


@router.post(
    "/api/project/{project_id}/files",
    response_model=List[File],
    status_code=status.HTTP_201_CREATED,
)
async def add_files_to_project(
    project_id: str,
    files: List[UploadFile] = FastAPIUploadFile(...),
    role: FileRole = Form(default=FileRole.SUPPORT),
    current_user: User = Depends(get_current_user),
):
    """Add files (supporting documents) to an existing project."""

    project = await get_user_project(project_id, user=current_user)
    roles = [role] * len(files)
    return await save_uploaded_files_to_db(
        uploaded_files=files,
        project_id=project.id,
        user_id=current_user.id,
        roles=roles,
    )


@router.post(
    "/api/project/{project_id}/file",
    response_model=File,
    status_code=status.HTTP_201_CREATED,
)
async def add_file_to_project(
    project_id: str,
    file: UploadFile = FastAPIUploadFile(...),
    reference_id: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user),
):
    """
    Add a single file (supporting document) to a project.

    Optionally link the file to a specific reference by providing reference_id
    (the ID of the reference from the ReferenceExtraction workflow state).
    """

    # Verify project access (user must be authenticated owner)
    project = await get_user_project(project_id, user=current_user)

    try:
        # Save the uploaded file with SUPPORT role
        file_records = await save_uploaded_files_to_db(
            uploaded_files=[file],
            project_id=project.id,
            user_id=current_user.id,
            roles=[FileRole.SUPPORT],
        )

        file_record = file_records[0]

        # If reference_id is provided, link the file to that reference
        if reference_id is not None:
            await add_file_to_reference(
                project_id=project_id,
                file_id=str(file_record.id),
                reference_id=reference_id,
            )

        return file_record

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to upload file: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file",
        )


@router.delete("/api/project/{project_id}/files/{file_id}")
async def delete_project_file_endpoint(
    project_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a file from a project and unlink it from any references."""

    # Verify project access (user must be authenticated owner)
    project = await get_user_project(project_id, user=current_user)

    # Delete the file from the project
    deleted_count = await delete_project_files(project.id, target_file_ids=[file_id])

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="File not found in project")

    # Update workflow state to remove file_id from references
    await remove_file_from_references(project_id, file_id)

    return {"message": "File deleted successfully", "file_id": file_id}


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
    project = await check_project_access(project_id, current_user, share_token)

    # Create zip file using service
    zip_buffer, _ = await create_project_files_zip(project_id, roles=roles)

    # Generate filename from project title
    project_title = project.title or "project"

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

    project = await check_project_access(project_id, current_user, share_token)
    progress_list = await get_project_workflow_progress(project.id)
    return [WorkflowProgressResponse.model_validate(p) for p in progress_list]


@router.get(
    "/api/project/{project_id}/workflow-runs",
    response_model=List[WorkflowRunDetail],
)
async def get_project_workflow_runs_by_type_endpoint(
    project_id: str,
    workflow_type: WorkflowRunType = Query(
        ...,
        description="The workflow type to filter runs by",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token for shared projects.",
    ),
):
    """
    Get all workflow runs of a specific type for a project.

    Returns workflow run details (including state with errors) ordered by creation date descending.
    Used for displaying workflow run history in the UI with correct error status.
    """

    await check_project_access(project_id, current_user, share_token)
    return await get_project_workflow_runs_by_type_with_details(
        project_id, workflow_type
    )


async def check_project_access(
    project_id: str,
    current_user: Optional[User] = None,
    share_token: Optional[str] = None,
) -> Project:
    """Check if a user or share token gives access to a project. Raises HTTPException if access is denied. Returns the project if access is granted."""

    if share_token:
        share_link = await get_resource_by_token(share_token)
        if share_link is None or str(share_link.resource_id) != project_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return await get_shared_project(str(share_link.resource_id))
    elif current_user is not None:
        return await get_user_project(project_id, user=current_user)
    else:
        raise HTTPException(status_code=403, detail="Access denied")
