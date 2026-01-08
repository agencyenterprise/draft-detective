import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi import File as FastAPIUploadFile
from fastapi import Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse

from api.auth import get_current_user
from api.upload import save_uploaded_files_to_db
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User
from lib.services.docx_workflow_service import get_or_generate_docx
from lib.services.files import (
    check_file_access,
    create_project_files_zip,
    delete_project_files,
)
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
    current_user: User = Depends(get_current_user),
):
    """
    Download DOCX with AI comments.

    Uses cached version if available, otherwise generates via workflow.
    First request may take a few seconds as it generates the DOCX.
    Subsequent requests with the same share_token (or none) are instant.
    """

    project_detail = await get_user_project_detailed(project_id, user=current_user)

    try:
        # Get cached or generate DOCX via workflow (with caching)
        file_path, filename = await get_or_generate_docx(
            project_id=str(project_detail.project.id),
            share_token=share_token,
            user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
    project_id: str, current_user: User = Depends(get_current_user)
):
    """Get all files for a project"""

    return await get_user_project_files(project_id, user=current_user)


@router.post("/api/project/{project_id}/files", response_model=List[File])
async def upload_project_files_endpoint(
    project_id: str,
    files: List[UploadFile] = FastAPIUploadFile(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload supporting files to an existing project.

    Accepts multiple files via multipart form data and saves them with SUPPORT role.
    Verifies that the user has access to the project before allowing uploads.

    Args:
        project_id: UUID of the project to add files to
        files: List of files to upload
        current_user: Authenticated user from JWT token

    Returns:
        List of created File records

    Raises:
        HTTPException: 404 if project not found, 403 if access denied, 400 for invalid files
    """
    # Verify project access
    await get_user_project_detailed(project_id, user=current_user)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        file_records = await save_uploaded_files_to_db(
            uploaded_files=files,
            project_id=uuid.UUID(project_id),
            user_id=current_user.id,
            roles=[FileRole.SUPPORT] * len(files),
        )

        logger.info(
            f"Uploaded {len(file_records)} supporting files to project {project_id}"
        )
        return file_records

    except ValueError as e:
        logger.error(f"Invalid file upload for project {project_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Failed to upload files to project {project_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload files",
        )


@router.delete("/api/project/{project_id}/files/{file_id}")
async def delete_project_file_endpoint(
    project_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a single file from a project.

    Verifies that the user has access to the file and prevents deletion of main files.
    Only supporting files can be deleted.

    Args:
        project_id: UUID of the project
        file_id: UUID of the file to delete
        current_user: Authenticated user from JWT token

    Returns:
        Success message

    Raises:
        HTTPException: 400 for invalid file ID or main file deletion, 404 if file not found, 403 if access denied
    """
    # Check access and get file record
    file = await check_file_access(file_id, current_user.id)

    # Prevent main file deletion
    if file.role == FileRole.MAIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete main file",
        )

    # Verify the file belongs to the specified project
    if str(file.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not belong to the specified project",
        )

    # Delete the file
    delete_project_files(project_id, target_file_ids=[file_id])

    logger.info(f"Deleted file {file_id} from project {project_id}")
    return {"message": "File deleted successfully", "file_id": file_id}


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
