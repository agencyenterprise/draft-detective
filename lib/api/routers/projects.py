import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from fastapi import HTTPException, Query, status
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse

from lib.api.auth import get_current_user, get_current_user_optional
from lib.api.models import (
    CreateRevisionResponse,
    LinkReferenceFileRequest,
    LinkReferenceFileResponse,
    RevisionListItem,
    WorkflowProgressResponse,
)
from lib.models.file import File, FileRole
from lib.models.project import AccessLevel, Project
from lib.models.user import User
from lib.services.docx_workflow_service import DocxManipulatorType, generate_docx
from lib.services.files import get_files_by_project_id
from lib.services.project_zip import create_project_files_zip
from lib.services.references import MatchSource, add_file_to_reference
from lib.services.uuid_utils import ensure_uuid
from lib.services.projects import (
    MAX_PROJECT_PAGE_SIZE,
    ProjectDetailed,
    ProjectListPage,
    UpdateProjectRequest,
    create_project,
    create_new_revision,
    delete_project,
    delete_project_file_with_cleanup,
    get_project_access,
    get_project_detailed_from_project,
    get_project_files,
    get_user_projects,
    update_user_project,
)
from lib.services.workflow_progress import get_project_workflow_progress
from lib.services.workflow_runs import (
    WorkflowRunDetail,
    get_project_workflow_runs_by_type_with_details,
)
from lib.models.workflow_run import WorkflowRunType
from lib.workflows.models import SeverityEnum
from lib.api.models import CreateProjectRequest

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
        return ProjectDetailed(
            project=project, access_level=AccessLevel.WRITE, workflow_runs=[]
        )
    except Exception as e:
        logger.error("Failed to create project: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )


@router.get("/api/projects", response_model=ProjectListPage)
async def list_projects_endpoint(
    search: Optional[str] = Query(
        default=None,
        description="Only projects whose title contains every whitespace-separated term",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=MAX_PROJECT_PAGE_SIZE,
        description="Maximum number of projects to return",
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of projects to skip for pagination"
    ),
    current_user: User = Depends(get_current_user),
):
    """List the current user's projects, newest activity first, one page at a time."""
    return await get_user_projects(
        user=current_user, search=search, limit=limit, offset=offset
    )


@router.get("/api/project/{project_id}", response_model=ProjectDetailed)
async def get_project_endpoint(
    project_id: str,
    include_internal: bool = False,
    revision: Optional[int] = Query(
        default=None,
        description="Revision number to return. Defaults to the project's current revision.",
    ),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token to get project details",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a project by ID. Set include_internal=true to see internal workflows."""

    project, access_level = await get_project_access(
        project_id, current_user, share_token
    )
    project_detailed = await get_project_detailed_from_project(
        project,
        access_level=access_level,
        include_internal=include_internal,
        user=current_user,
        revision=revision,
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
    docx_type: DocxManipulatorType | Literal["original"] = Query(
        default="original",
        description="Docx type",
    ),
    include_passing: bool = Query(
        default=False,
        description="Include passing issues (severity=none) in the export",
    ),
    include_edits: bool = Query(
        default=True,
        description=(
            "Apply the issues' proposed edits as Word tracked changes, so they "
            "can be accepted or rejected in Word. Comment exports only."
        ),
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Download DOCX with AI comments. Always regenerates from scratch."""

    await get_project_access(project_id, current_user, share_token)

    try:
        file_path, filename = await generate_docx(
            project_id=project_id,
            share_token=share_token,
            severities=severities,
            workflow_types=workflow_types,
            docx_type=docx_type,
            include_passing=include_passing,
            include_edits=include_edits,
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

    await get_project_access(project_id, current_user, share_token)
    return await get_project_files(project_id)


@router.delete("/api/project/{project_id}/files/{file_id}")
async def delete_project_file_endpoint(
    project_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a file from a project and unlink it from any references."""

    project, _ = await get_project_access(
        project_id, user=current_user, required_level=AccessLevel.WRITE
    )

    deleted_count, _ = await delete_project_file_with_cleanup(
        project_id, file_id, revision=project.current_revision
    )

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="File not found in project")

    return {"message": "File deleted successfully", "file_id": file_id}


@router.post(
    "/api/project/{project_id}/references/{reference_id}/files",
    response_model=LinkReferenceFileResponse,
)
async def link_reference_file_endpoint(
    project_id: str,
    reference_id: str,
    request: LinkReferenceFileRequest,
    current_user: User = Depends(get_current_user),
):
    """Link an already-uploaded supporting file to an extracted reference.

    The app can already do this at upload time, by putting a `reference_id` in
    the TUS metadata. This is the same operation for a file that is already in
    the project, so a user can correct or supply a match without re-uploading.

    The link is recorded as `MANUAL_UPLOAD`, which takes precedence over
    whatever the automatic matcher decided. Re-posting for the same reference
    replaces the previous match rather than adding a second one.
    """
    project, _ = await get_project_access(
        project_id, user=current_user, required_level=AccessLevel.WRITE
    )

    # Compare as UUIDs, not as text: File.id is a real uuid.UUID, so matching
    # the raw string would reject an equivalent spelling (e.g. upper-case) and
    # report a malformed id as "not found". ensure_uuid raises 400 instead.
    #
    # reference_id is deliberately left as-is: ExtractedReference.id is an
    # opaque str, not a UUID, so exact matching is the right check there and
    # the service already does it.
    file_uuid = ensure_uuid(request.file_id, "file ID")

    # The service validates reference_id against the extraction state, but not
    # the file, so check it here: it has to be a supporting file of this
    # project's current revision.
    supporting_files = await get_files_by_project_id(
        project_id,
        roles=[FileRole.SUPPORT],
        revision=project.current_revision,
    )
    if file_uuid not in {f.id for f in supporting_files}:
        raise HTTPException(
            status_code=404,
            detail="Supporting file not found in this project's current revision",
        )

    linked = await add_file_to_reference(
        project_id=project_id,
        file_id=str(file_uuid),
        reference_id=reference_id,
        source=MatchSource.MANUAL_UPLOAD,
        revision=project.current_revision,
    )
    if not linked:
        # add_file_to_reference returns False when the reference is unknown for
        # this revision, or when references have not been extracted yet.
        raise HTTPException(
            status_code=409,
            detail=(
                "Could not link the file to that reference. The reference is "
                "unknown for the current revision, or reference extraction has "
                "not run yet."
            ),
        )

    # Echo the canonical spelling that was stored, not whatever was sent.
    return LinkReferenceFileResponse(reference_id=reference_id, file_id=str(file_uuid))


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
    project, _ = await get_project_access(project_id, current_user, share_token)

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
    revision: Optional[int] = Query(
        default=None,
        description="Revision number. Defaults to the project's current revision.",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token for shared projects.",
    ),
):
    """Get all workflow progress entries for a project."""

    project, _ = await get_project_access(project_id, current_user, share_token)
    resolved_revision = revision if revision is not None else project.current_revision
    progress_list = await get_project_workflow_progress(
        project.id, revision=resolved_revision
    )
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

    project, _ = await get_project_access(project_id, current_user, share_token)
    return await get_project_workflow_runs_by_type_with_details(
        project_id, workflow_type, revision=project.current_revision
    )


@router.post(
    "/api/project/{project_id}/revisions",
    response_model=CreateRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Create a new revision for a project.

    Archives active issues from the current revision, cancels running workflows,
    and increments the revision counter. The new main document should be uploaded
    via the TUS upload endpoint after this call.
    """
    new_revision, previous_types = await create_new_revision(project_id, current_user)
    return CreateRevisionResponse(
        revision=new_revision,
        previous_workflow_types=previous_types,
    )


@router.get(
    "/api/project/{project_id}/revisions",
    response_model=List[RevisionListItem],
)
async def list_revisions_endpoint(
    project_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    share_token: Optional[str] = Query(
        default=None,
        description="Share token for shared projects.",
    ),
):
    """List all revisions for a project with their main file info."""
    project, _ = await get_project_access(project_id, current_user, share_token)

    # Get all MAIN files to build revision list
    main_files = await get_files_by_project_id(project_id, roles=[FileRole.MAIN])
    main_file_by_revision: dict[int, File] = {}
    for f in main_files:
        if f.revision is not None:
            main_file_by_revision[f.revision] = f

    revisions = []
    for rev in range(1, project.current_revision + 1):
        main_file = main_file_by_revision.get(rev)
        revisions.append(
            RevisionListItem(
                revision=rev,
                main_file_name=main_file.file_name if main_file else None,
                main_file_id=str(main_file.id) if main_file else None,
                created_at=main_file.created_at if main_file else None,
            )
        )

    return revisions
