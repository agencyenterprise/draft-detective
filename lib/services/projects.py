from collections import defaultdict
import logging
from typing import List, Optional

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update

from lib.config.database import get_db
from lib.models.project import Project
from lib.models.file import File
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.files import delete_project_files
from lib.services.workflow_runs import get_project_workflow_runs
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.models import is_user_visible_workflow

logger = logging.getLogger(__name__)


class ProjectListItem(BaseModel):
    project: Project = Field(description="The project")
    workflow_runs: List[WorkflowRun] = Field(
        default_factory=list,
        description="The workflow runs for the project",
    )


class ProjectDetailed(BaseModel):
    project: Project
    workflow_runs: List[WorkflowRun] = Field(
        default_factory=list,
        description="The workflow runs for the project",
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


async def get_user_project_detailed(project_id: str, user: User) -> ProjectDetailed:
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id is None or project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    workflow_runs = await get_project_workflow_runs(project.id)

    # We must filter out internal workflows
    visible_workflow_runs = [
        run for run in workflow_runs if is_user_visible_workflow(run.type)
    ]
    return ProjectDetailed(project=project, workflow_runs=visible_workflow_runs)


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
