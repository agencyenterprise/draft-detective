from datetime import date
import logging
import uuid
from collections import defaultdict
from typing import List, Optional, Sequence

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.feedback import FeedbackType
from lib.models.file import File, FileListItem, FileRole
from lib.models.issue import Issue
from lib.models.project import AccessLevel, FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import (
    ACTIVE_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
)
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.files import (
    delete_project_files,
    get_files_by_project_id,
    get_project_files_list_items,
)
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
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import available_workflow_type_values, get_all_manifests

logger = logging.getLogger(__name__)

MAX_PROJECT_PAGE_SIZE = 200


class ProjectListItem(BaseModel):
    project: Project = Field(description="The project")
    workflow_runs: List[WorkflowRun] = Field(
        default_factory=list,
        description="The workflow runs for the project",
    )


class ProjectListPage(BaseModel):
    items: List[ProjectListItem] = Field(description="The projects on this page")
    total: int = Field(description="Number of projects matching the query overall")
    limit: int = Field(description="Page size that was applied")
    offset: int = Field(description="Number of projects skipped before this page")


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
    feedback_visibility: Optional[FeedbackVisibility] = None


async def create_project(
    title: str,
    user: User,
    publication_date: date | None = None,
) -> Project:
    async with get_async_db_session() as session:
        project = Project(
            title=title,
            user_id=user.id,
            publication_date=publication_date,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


def _user_projects_query(user: User, search: Optional[str]) -> Select[tuple[Project]]:
    """Projects owned by ``user``, narrowed by every whitespace-separated search term."""
    stmt = select(Project).where(col(Project.user_id) == user.id)
    for term in (search or "").split():
        stmt = stmt.where(col(Project.title).ilike(f"%{term}%"))
    return stmt


async def _count_user_projects(
    session: AsyncSession, user: User, search: Optional[str]
) -> int:
    count_stmt = select(func.count()).select_from(
        _user_projects_query(user, search).subquery()
    )
    return (await session.execute(count_stmt)).scalar_one()


async def _live_runs_by_project(
    session: AsyncSession, project_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[WorkflowRun]]:
    """Current-revision runs of live workflow types, grouped by project."""
    runs_by_project: dict[uuid.UUID, list[WorkflowRun]] = defaultdict(list)
    if not project_ids:
        return runs_by_project
    stmt = (
        select(WorkflowRun)
        .join(Project, col(Project.id) == col(WorkflowRun.project_id))
        .where(col(WorkflowRun.project_id).in_(project_ids))
        .where(col(WorkflowRun.revision) == col(Project.current_revision))
        # Retired types have no manifest to render under, so they are hidden.
        .where(col(WorkflowRun.type).in_(available_workflow_type_values()))
        .order_by(col(WorkflowRun.created_at).asc())
    )
    for run in (await session.execute(stmt)).scalars().all():
        if run.project_id is not None:
            runs_by_project[run.project_id].append(run)
    return runs_by_project


async def get_user_projects(
    user: User,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> ProjectListPage:
    """One page of a user's projects, newest activity first, with their live runs.

    Projects are paged on their own before runs are attached, so a project with
    many runs never eats into the page size and the total counts projects.
    ``limit`` is clamped to [1, MAX_PROJECT_PAGE_SIZE] and ``offset`` to >= 0 so
    no caller can produce an unbounded or invalid query; the applied values are
    echoed back in the page.
    """
    limit = min(max(limit, 1), MAX_PROJECT_PAGE_SIZE)
    offset = max(offset, 0)

    async with get_async_db_session() as session:
        total = await _count_user_projects(session, user, search)
        page_stmt = (
            _user_projects_query(user, search)
            .order_by(col(Project.last_updated_at).desc(), col(Project.id).desc())
            .limit(limit)
            .offset(offset)
        )
        projects = list((await session.execute(page_stmt)).scalars().all())
        runs_by_project = await _live_runs_by_project(
            session, [project.id for project in projects]
        )
        return ProjectListPage(
            items=[
                ProjectListItem(
                    project=project, workflow_runs=runs_by_project[project.id]
                )
                for project in projects
            ],
            total=total,
            limit=limit,
            offset=offset,
        )


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

    The files list always includes every revision (each main-document revision
    plus shared supporting files); the current main is the one whose revision
    matches project.current_revision. Issues, workflow runs, and markdown stay
    scoped to the resolved revision.

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
        files=await get_project_files_list_items(project.id),
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
    """Get a project's uploaded documents — not transient supporting
    candidates or derived artifacts like extracted images. Raises
    HTTPException if project not found."""

    async with get_async_db_session() as session:
        project_stmt = select(Project).where(col(Project.id) == project_id)
        project = (await session.execute(project_stmt)).scalar_one_or_none()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        files_stmt = (
            select(File)
            .where(
                col(File.project_id) == project.id,
                col(File.role).in_(
                    [FileRole.MAIN, FileRole.SUPPORT, FileRole.REVIEWER_MEMO]
                ),
            )
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
            col(WorkflowRun.status).in_(ACTIVE_WORKFLOW_RUN_STATUSES),
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
        ran_before: list[WorkflowRunType] = []
        for row in result.all():
            if not isinstance(row[0], str):
                ran_before.append(row[0])
                continue
            try:
                ran_before.append(WorkflowRunType(row[0]))
            except ValueError:
                # Retired/unknown type still present in old rows — there is no
                # workflow left to re-run, so drop it instead of failing the
                # whole revision.
                logger.warning(
                    f"Skipping unknown workflow type {row[0]!r} from revision "
                    f"{old_revision} of project {project_id}"
                )
        # Workflows can opt out of being re-run automatically. The peer-review
        # ones do: they read the *reviewed* revision against the current draft,
        # so firing them the moment a revision is created either wastes an
        # expensive run or returns a guard message. The user starts them from
        # the Peer Review tab once the new draft is in place.
        #
        # An enum value whose manifest has been retired has nothing left to run,
        # so it is dropped here too — the enum member outlives the workflow so
        # old rows keep deserializing.
        manifests = get_all_manifests()
        previous_workflow_types = [
            workflow_type
            for workflow_type in ran_before
            if workflow_type in manifests
            and manifests[workflow_type].auto_rerun_on_new_revision
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

        await session.delete(project)
        await session.commit()
