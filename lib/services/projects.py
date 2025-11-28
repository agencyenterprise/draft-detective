import logging
from typing import List, Optional, Tuple

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update

from lib.config.database import get_db
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_runs import WorkflowRunDetailed, get_summary_state
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)


class ProjectListItem(BaseModel):
    project: Project = Field(description="The project")
    status: Optional[WorkflowRunStatus] = Field(
        default=WorkflowRunStatus.PENDING,
        description="The status of the associated workflow run",
    )


class ProjectDetailed(BaseModel):
    project: Project
    workflow_run: Optional[WorkflowRunDetailed] = None


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
    """Retrieve all projects for a user."""

    with get_db() as db:
        items: List[Tuple[Project, WorkflowRunStatus]] = (
            db.query(Project, WorkflowRun.status)
            .filter(Project.user_id == user.id)
            # TODO: we have only 1 workflow run per project for now, but this needs to be changed later
            .outerjoin(WorkflowRun)
            .order_by(Project.created_at.desc())
            .limit(100)
            .all()
        )

    return [ProjectListItem(project=item[0], status=item[1]) for item in items]


async def get_user_project_detailed(project_id: str, user: User) -> ProjectDetailed:
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id is None or project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # TODO: get ALL workflow runs for the project
    run = db.query(WorkflowRun).filter(WorkflowRun.project_id == project.id).first()

    if run is not None:
        workflow_run = WorkflowRunDetailed(
            run=run, state=await get_summary_state(run.langgraph_thread_id)
        )
    else:
        workflow_run = None

    return ProjectDetailed(project=project, workflow_run=workflow_run)


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
