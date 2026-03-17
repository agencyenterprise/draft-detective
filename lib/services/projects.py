from datetime import date
import logging
import uuid
from collections import defaultdict
from typing import List, Optional

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.feedback import FeedbackType
from lib.models.file import File, FileListItem
from lib.models.issue import Issue
from lib.models.project import FeedbackVisibility, Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.files import delete_project_files, get_project_files_list_items
from lib.services.issue_persistence import get_project_issues
from lib.services.share_links import is_project_shared
from lib.services.workflow_runs import WorkflowRunDetail, get_project_workflow_runs
from lib.workflows.checkpointer import get_checkpointer
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
            .outerjoin(WorkflowRun, col(WorkflowRun.project_id) == col(Project.id))
            .where(col(Project.user_id) == user.id)
            .order_by(col(Project.created_at).desc(), col(WorkflowRun.created_at).asc())
            .limit(200)
        )
        results = (await session.execute(stmt)).all()

        projects_dict = defaultdict(lambda: {"project": None, "workflow_runs": []})
        for row in results:
            project, workflow_run = row.tuple()
            if projects_dict[project.id]["project"] is None:
                projects_dict[project.id]["project"] = project
            if workflow_run is not None:
                projects_dict[project.id]["workflow_runs"].append(workflow_run)

        # Build the result list
        return [
            ProjectListItem(
                project=item["project"], workflow_runs=item["workflow_runs"]
            )
            for item in projects_dict.values()
        ]


async def _get_project_by_id(project_id: str) -> Project | None:
    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_project_detailed_from_project(
    project: Project,
    include_internal: bool = False,
    user: Optional[User] = None,
) -> ProjectDetailed:
    """
    Get detailed project information with workflow runs.

    Args:
        project: The project to get details for
        include_internal: If True, include internal workflows in the response
        user: If provided, load all feedback for this user on the project
    """
    from lib.services import feedback_service

    workflow_runs = await get_project_workflow_runs(
        project.id, include_internal=include_internal
    )

    # Clear out some heavy data from the workflow runs to reduce payload size
    # TODO: we should have a better way to do this
    for run in workflow_runs:
        if (
            run.run.type == WorkflowRunType.DOCUMENT_PROCESSING
            and run.state
            and run.state.file
        ):
            run.state.file.markdown = None
            for supporting_file in run.state.supporting_files:
                supporting_file.markdown = None

    # Query persisted issues from the database (faster than computing from state)
    issues = await get_project_issues(uuid.UUID(str(project.id)))

    feedbacks: list[FeedbackSummary] = []
    if user is not None:
        async with get_async_db_session() as session:
            feedback_models = await feedback_service.get_project_feedbacks(
                session=session, project_id=project.id, user=user
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

    return ProjectDetailed(
        project=project,
        workflow_runs=workflow_runs,
        issues=list(issues),
        files=await get_project_files_list_items(project.id),
        feedbacks=feedbacks,
    )


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


async def get_user_project(project_id: str, user: User) -> Project:
    """
    Get a project for a user.

    Args:
        project_id: The ID of the project
        user: The user

    Returns:
        The project

    Raises:
        HTTPException: 404 if project not found, 403 if user does not have access
    """

    project = await _get_project_by_id(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return project


async def get_project_files(project_id: str) -> List[File]:
    """Get all files for a project. Raises HTTPException if project not found."""

    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        stmt = (
            select(File)
            .where(col(File.project_id) == project.id)
            .order_by(col(File.created_at).asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def update_user_project(
    project_id: str, request: UpdateProjectRequest, user: User
) -> Project:
    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.user_id is None or project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

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


async def delete_project(project_id: str, user: User) -> None:
    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.user_id is None or project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        await delete_project_files(project_id)

        stmt = select(WorkflowRun).where(col(WorkflowRun.project_id) == project_id)
        result = await session.execute(stmt)
        project_workflow_runs = result.scalars().all()
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
