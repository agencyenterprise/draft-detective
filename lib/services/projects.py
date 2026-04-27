from datetime import date
import logging
import uuid
from collections import defaultdict
from typing import List, Optional, Sequence

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.feedback import FeedbackType
from lib.models.file import File, FileListItem, FileRole
from lib.models.issue import Issue
from lib.models.project import AccessLevel, FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.files import (
    delete_project_files,
    get_files_by_project_id,
    get_project_files_list_items,
)
from lib.services.chunk_line_matcher import find_line_range_by_chunks
from lib.services.issue_persistence import get_project_issues
from lib.services.references import (
    remove_fetch_result_for_file,
    remove_file_from_references,
)
from lib.services.share_links import get_resource_by_token, is_project_shared
from lib.services.workflow_runs import (
    WorkflowRunDetail,
    cancel_workflow_run,
    get_project_workflow_runs,
)
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowRunType

logger = logging.getLogger(__name__)


class ProjectListItem(BaseModel):
    project: Project = Field(description="The project")
    workflow_runs: List[WorkflowRun] = Field(
        default_factory=list,
        description="The workflow runs for the project",
    )


class FeedbackSummary(BaseModel):
    """Lightweight feedback representation for project detail responses."""

    id: str
    workflow_run_id: str
    entity_path: dict
    feedback_type: FeedbackType
    feedback_text: Optional[str] = None
    created_at: str
    updated_at: str


class ProjectDetailed(BaseModel):
    project: Project
    access_level: AccessLevel = Field(
        description="The access level of the current user for this project",
    )
    workflow_runs: List[WorkflowRunDetail] = Field(
        default_factory=list,
        description="The workflow runs for the project",
    )
    issues: List[Issue] = Field(
        default_factory=list,
        description="The persisted issues for the project",
    )
    files: List[FileListItem] = Field(
        default_factory=list,
        description="The files associated with the project",
    )
    feedbacks: List[FeedbackSummary] = Field(
        default_factory=list,
        description="All user feedback for this project's workflow runs",
    )
    revision: int = Field(
        default=1,
        description="The revision being returned",
    )
    main_document_markdown: Optional[str] = Field(
        default=None,
        description="Full markdown of the main document for this revision, if available",
    )


class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    publication_date: Optional[date] = None
    domain: Optional[str] = None
    target_audience: Optional[str] = None
    feedback_visibility: Optional[FeedbackVisibility] = None


async def create_project(
    title: str,
    user: User,
    publication_date: date | None = None,
    domain: str | None = None,
    target_audience: str | None = None,
) -> Project:
    async with get_async_db_session() as session:
        project = Project(
            title=title,
            user_id=user.id,
            publication_date=publication_date,
            domain=domain,
            target_audience=target_audience,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


async def get_user_projects(user: User) -> List[ProjectListItem]:
    """Retrieve all projects for a user with their associated workflow runs."""

    async with get_async_db_session() as session:
        stmt = (
            select(Project, WorkflowRun)
            .outerjoin(
                WorkflowRun,
                and_(
                    col(WorkflowRun.project_id) == col(Project.id),
                    col(WorkflowRun.revision) == col(Project.current_revision),
                ),
            )
            .where(col(Project.user_id) == user.id)
            .order_by(col(Project.created_at).desc(), col(WorkflowRun.created_at).asc())
            .limit(200)
        )
        results = (await session.execute(stmt)).all()

        projects_by_id: dict[uuid.UUID, Project] = {}
        runs_by_project: dict[uuid.UUID, list[WorkflowRun]] = defaultdict(list)
        for row in results:
            project, workflow_run = row.tuple()
            projects_by_id.setdefault(project.id, project)
            if workflow_run is not None:
                runs_by_project[project.id].append(workflow_run)

        # Build the result list
        return [
            ProjectListItem(project=project, workflow_runs=runs_by_project[project.id])
            for project in projects_by_id.values()
        ]


async def _get_project_by_id(project_id: str) -> Project | None:
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        return None

    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project_uuid)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_project_detailed_from_project(
    project: Project,
    access_level: AccessLevel,
    include_internal: bool = False,
    user: Optional[User] = None,
    revision: int | None = None,
) -> ProjectDetailed:
    """
    Get detailed project information with workflow runs.

    Args:
        project: The project to get details for
        access_level: The access level of the current user
        include_internal: If True, include internal workflows in the response
        user: If provided, load all feedback for this user on the project
        revision: If provided, return data for this revision. Defaults to current_revision.
    """
    from lib.services import feedback_service

    resolved_revision = revision if revision is not None else project.current_revision

    workflow_runs = await get_project_workflow_runs(
        str(project.id), revision=resolved_revision, include_internal=include_internal
    )

    # Clear out some heavy data from the workflow runs to reduce payload size
    # TODO: we should have a better way to do this. `markdown` is declared
    # `str` but we blank it here to shrink the serialized payload.
    for run in workflow_runs:
        if isinstance(run.state, DocumentProcessingState) and run.state.file:
            run.state.file.markdown = None  # type: ignore[assignment]
            for supporting_file in run.state.supporting_files or []:
                supporting_file.markdown = None  # type: ignore[assignment]

    # Query persisted issues from the database (faster than computing from state)
    issues = await get_project_issues(
        uuid.UUID(str(project.id)), revision=resolved_revision
    )

    # For issues persisted before the line-range migration, derive
    # (start_line, end_line) on-the-fly from their chunk_indices so the
    # markdown renderer can locate them.
    _backfill_issue_line_ranges(issues, workflow_runs)

    feedbacks: list[FeedbackSummary] = []
    if user is not None:
        async with get_async_db_session() as session:
            feedback_models = await feedback_service.get_project_feedbacks(
                session=session,
                project_id=project.id,
                user=user,
                revision=resolved_revision,
            )
            feedbacks = [
                FeedbackSummary(
                    id=str(f.id),
                    workflow_run_id=str(f.workflow_run_id),
                    entity_path=f.entity_path,
                    feedback_type=f.feedback_type,
                    feedback_text=f.feedback_text,
                    created_at=f.created_at.isoformat(),
                    updated_at=f.updated_at.isoformat(),
                )
                for f in feedback_models
            ]

    main_document_markdown = await _get_main_document_markdown(
        str(project.id), resolved_revision
    )

    return ProjectDetailed(
        project=project,
        access_level=access_level,
        workflow_runs=workflow_runs,
        issues=list(issues),
        files=await get_project_files_list_items(
            project.id, revision=resolved_revision
        ),
        feedbacks=feedbacks,
        revision=resolved_revision,
        main_document_markdown=main_document_markdown,
    )


async def _get_main_document_markdown(project_id: str, revision: int) -> Optional[str]:
    """Load the full markdown of the main document for a revision, or None if
    it isn't available yet (e.g. before document processing completes)."""
    main_files = await get_files_by_project_id(
        project_id, roles=[FileRole.MAIN], revision=revision
    )
    if not main_files:
        return None
    artifacts = FileArtifactsService(project_id, revision=revision)
    try:
        file_document = await artifacts.get_file_document(str(main_files[0].id))
    except ValueError:
        return None
    return file_document.markdown


def _backfill_issue_line_ranges(
    issues: Sequence[Issue], workflow_runs: List[WorkflowRunDetail]
) -> None:
    """Derive (start_line, end_line) from chunk_indices for issues persisted
    before the line-range migration. Mutates issues in place."""
    chunks = None
    for detail in workflow_runs:
        if (
            detail.state is not None
            and detail.state.type == WorkflowRunType.CHUNK_SPLITTING
        ):
            chunks = getattr(detail.state, "chunks", None) or None
            break
    if not chunks:
        return

    for issue in issues:
        if issue.start_line is not None or issue.end_line is not None:
            continue
        if not issue.chunk_indices:
            continue
        line_range = find_line_range_by_chunks(chunks, issue.chunk_indices)
        if line_range is not None:
            issue.start_line, issue.end_line = line_range


async def get_shared_project(project_id: str) -> Project:
    """
    Get a project for a shared project.

    Args:
        project_id: The ID of the project

    Returns:
        The project

    Raises:
        HTTPException: 404 if project not found, 403 if project is not shared
    """

    project = await _get_project_by_id(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await is_project_shared(project_id):
        raise HTTPException(status_code=403, detail="Project is not shared")

    return project


async def get_project_access(
    project_id: str,
    user: Optional[User] = None,
    share_token: Optional[str] = None,
    required_level: AccessLevel = AccessLevel.READ,
) -> tuple[Project, AccessLevel]:
    """
    Central permission gate for project access.

    Access is resolved in priority order:
    1. Project owner → WRITE
    2. Admin + feedback_visibility=full_project → READ
    3. Valid share token → READ

    Args:
        project_id: The ID of the project
        user: The authenticated user, if any
        share_token: A share token, if provided (only grants READ; always evaluated but will never satisfy required_level=WRITE)
        required_level: Minimum access level required; raises 403 if resolved level is insufficient

    Returns:
        A tuple of (project, access_level)

    Raises:
        HTTPException: 404 if project not found, 403 if access is denied or insufficient
    """
    project = await _get_project_by_id(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    access_level: Optional[AccessLevel] = None

    if user is not None and project.user_id == user.id:
        access_level = AccessLevel.WRITE
    elif (
        user is not None
        and user.role == UserRole.ADMIN
        and project.feedback_visibility == FeedbackVisibility.FULL_PROJECT
    ):
        access_level = AccessLevel.READ
    elif share_token is not None:
        share_link = await get_resource_by_token(share_token)
        if share_link is not None and str(share_link.resource_id) == project_id:
            access_level = AccessLevel.READ

    if access_level is None:
        raise HTTPException(status_code=403, detail="Access denied")

    if required_level == AccessLevel.WRITE and access_level != AccessLevel.WRITE:
        raise HTTPException(status_code=403, detail="Write access required")

    return project, access_level


async def get_project_files(project_id: str) -> List[File]:
    """Get all files for a project. Raises HTTPException if project not found."""

    async with get_async_db_session() as session:
        project_stmt = select(Project).where(col(Project.id) == project_id)
        project = (await session.execute(project_stmt)).scalar_one_or_none()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        files_stmt = (
            select(File)
            .where(col(File.project_id) == project.id)
            .order_by(col(File.created_at).asc())
        )
        files_result = await session.execute(files_stmt)
        return list(files_result.scalars().all())


async def delete_project_file_with_cleanup(
    project_id: str, file_id: str, revision: int
) -> tuple[int, List[str]]:
    """
    Delete a file from a project and clean up all references to it.

    Performs three steps:
    1. Delete the file record and its disk content (unless shared with another project)
    2. Unlink the file from any ReferenceFileMatching matches
    3. Clear any ReferenceDownloader fetch result that pointed at this file

    Returns:
        (deleted_count, removed_reference_ids): number of files actually deleted and the
        list of reference IDs that were unlinked from the file.
    """
    deleted_count = await delete_project_files(project_id, target_file_ids=[file_id])
    if deleted_count == 0:
        return 0, []

    removed_reference_ids = await remove_file_from_references(
        project_id, file_id, revision=revision
    )
    await remove_fetch_result_for_file(project_id, file_id, revision=revision)

    return deleted_count, removed_reference_ids


async def update_user_project(
    project_id: str, request: UpdateProjectRequest, user: User
) -> Project:
    await get_project_access(project_id, user=user, required_level=AccessLevel.WRITE)

    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one()

        if request.title is not None:
            project.title = request.title

        project.publication_date = request.publication_date
        project.domain = request.domain
        project.target_audience = request.target_audience

        if request.feedback_visibility is not None:
            project.feedback_visibility = request.feedback_visibility

        await session.commit()
        await session.refresh(project)
        return project


async def update_project_title(project_id: str, title: str) -> None:
    async with get_async_db_session() as session:
        await session.execute(
            update(Project).where(col(Project.id) == project_id).values(title=title)
        )
        await session.commit()


async def create_new_revision(
    project_id: str, user: User
) -> tuple[int, List[WorkflowRunType]]:
    """
    Create a new revision for a project.

    Archives active issues from the current revision, cancels running workflows,
    increments the revision counter, and returns the new revision number along with
    the workflow types that were previously run (for re-triggering).
    """
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.WRITE
    )

    old_revision = project.current_revision
    new_revision = old_revision + 1

    async with get_async_db_session() as session:
        # Cancel any active workflows for the old revision
        active_runs_stmt = select(WorkflowRun).where(
            col(WorkflowRun.project_id) == project_id,
            col(WorkflowRun.revision) == old_revision,
            col(WorkflowRun.status).in_(
                [WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING]
            ),
        )
        active_runs = (await session.execute(active_runs_stmt)).scalars().all()

    for run in active_runs:
        await cancel_workflow_run(str(run.id), project_id)

    async with get_async_db_session() as session:
        # Collect previous workflow types
        types_stmt = (
            select(col(WorkflowRun.type))
            .where(
                col(WorkflowRun.project_id) == project_id,
                col(WorkflowRun.revision) == old_revision,
            )
            .distinct()
        )
        result = await session.execute(types_stmt)
        previous_workflow_types = [
            WorkflowRunType(row[0]) if isinstance(row[0], str) else row[0]
            for row in result.all()
        ]

        # Increment project revision
        await session.execute(
            update(Project)
            .where(col(Project.id) == project_id)
            .values(current_revision=new_revision)
        )

        await session.commit()

    logger.info(
        f"Created revision {new_revision} for project {project_id} "
        f"(previous types: {[str(t) for t in previous_workflow_types]})"
    )

    return new_revision, previous_workflow_types


async def delete_project(project_id: str, user: User) -> None:
    await get_project_access(project_id, user=user, required_level=AccessLevel.WRITE)

    async with get_async_db_session() as session:
        project_stmt = select(Project).where(col(Project.id) == project_id)
        project = (await session.execute(project_stmt)).scalar_one()

        await delete_project_files(project_id)

        runs_stmt = select(WorkflowRun).where(col(WorkflowRun.project_id) == project_id)
        project_workflow_runs = (await session.execute(runs_stmt)).scalars().all()
        thread_ids = [
            workflow_run.langgraph_thread_id for workflow_run in project_workflow_runs
        ]

        await session.delete(project)
        await session.commit()

    try:
        async with get_checkpointer() as checkpointer:
            for thread_id in thread_ids:
                await checkpointer.adelete_thread(thread_id)
    except Exception as e:
        logger.error(
            f"Error deleting checkpoints for threads {', '.join(thread_ids)}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error deleting checkpoint data: {str(e)}"
        )
