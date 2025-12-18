import logging
from collections import defaultdict
from typing import List, Optional

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update

from lib.config.database import get_db
from lib.models.file import File
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.files import delete_project_files
from lib.services.issues import convert_to_issues
from lib.services.share_links import is_project_shared
from lib.services.workflow_runs import WorkflowRunDetail, get_project_workflow_runs
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.models import DocumentIssue, is_user_visible_workflow

logger = logging.getLogger(__name__)


class ProjectListItem(BaseModel):
    project: Project = Field(description="The project")
    workflow_runs: List[WorkflowRun] = Field(
        default_factory=list,
        description="The workflow runs for the project",
    )


class ProjectDetailed(BaseModel):
    project: Project
    workflow_runs: List[WorkflowRunDetail] = Field(
        default_factory=list,
        description="The workflow runs for the project",
    )
    issues: List[DocumentIssue] = Field(
        default_factory=list,
        description="The issues for the project, converted from the workflow results states",
    )


class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None


async def create_project(title: str, user: User) -> Project:
    with get_db() as db:
        project = Project(title=title, user_id=user.id)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project


async def get_user_projects(user: User) -> List[ProjectListItem]:
    """Retrieve all projects for a user with their associated workflow runs."""

    with get_db() as db:
        results = (
            db.query(Project, WorkflowRun)
            .outerjoin(WorkflowRun, WorkflowRun.project_id == Project.id)
            .filter(Project.user_id == user.id)
            .order_by(Project.created_at.desc(), WorkflowRun.created_at.asc())
            .limit(200)
            .all()
        )

        if not results:
            return []

        # We need to group workflow runs by project, filtering out internal workflows
        projects_dict = defaultdict(lambda: {"project": None, "workflow_runs": []})
        for project, workflow_run in results:
            if projects_dict[project.id]["project"] is None:
                projects_dict[project.id]["project"] = project
            if workflow_run is not None and is_user_visible_workflow(workflow_run.type):
                projects_dict[project.id]["workflow_runs"].append(workflow_run)

        # Build the result list
        return [
            ProjectListItem(
                project=item["project"], workflow_runs=item["workflow_runs"]
            )
            for item in projects_dict.values()
        ]


async def _get_project_by_id(project_id: str) -> Project | None:
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

    return project


async def _get_project_detailed_from_project(project: Project) -> ProjectDetailed:
    workflow_runs = await get_project_workflow_runs(project.id)

    # We must filter out internal workflows
    visible_workflow_runs = [
        item for item in workflow_runs if is_user_visible_workflow(item.run.type)
    ]
    states = [run.state for run in visible_workflow_runs if run.state is not None]
    return ProjectDetailed(
        project=project,
        workflow_runs=visible_workflow_runs,
        issues=convert_to_issues(states),
    )


async def get_shared_project_detailed(project_id: str) -> ProjectDetailed:
    """
    Get a project detailed for a shared project.

    Args:
        project_id: The ID of the project

    Returns:
        The project detailed

    Raises:
        HTTPException: 404 if project not found, 403 if project is not shared
    """

    project = await _get_project_by_id(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await is_project_shared(project_id):
        raise HTTPException(status_code=403, detail="Project is not shared")

    return await _get_project_detailed_from_project(project)


async def get_user_project_detailed(project_id: str, user: User) -> ProjectDetailed:
    """
    Get a project detailed for a user.

    Args:
        project_id: The ID of the project
        user: The user

    Returns:
        The project detailed

    Raises:
        HTTPException: 404 if project not found, 403 if user does not have access
    """

    project = await _get_project_by_id(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return await _get_project_detailed_from_project(project)


async def get_user_project_files(project_id: str, user: User) -> List[File]:
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.user_id is None or project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return (
            db.query(File)
            .filter(File.project_id == project.id)
            .order_by(File.created_at.asc())
            .all()
        )


async def update_user_project(
    project_id: str, request: UpdateProjectRequest, user: User
) -> Project:
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.user_id is None or project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        if request.title is not None:
            project.title = request.title

        db.commit()
        db.refresh(project)
        return project


async def update_project_title(project_id: str, title: str) -> Project:
    with get_db() as db:
        db.execute(update(Project).where(Project.id == project_id).values(title=title))
        db.commit()


async def delete_project(project_id: str, user: User) -> None:
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.user_id is None or project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        delete_project_files(project_id)

        project_workflow_runs = (
            db.query(WorkflowRun).filter(WorkflowRun.project_id == project_id).all()
        )
        thread_ids = [
            workflow_run.langgraph_thread_id for workflow_run in project_workflow_runs
        ]

        db.delete(project)
        db.commit()

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
