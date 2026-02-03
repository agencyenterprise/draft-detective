from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.share_link import ShareLink
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun


async def has_access_to_workflow_run(
    user: Optional[User], workflow_run_id: str
) -> bool:
    """Check if a user has access to a workflow run, either by being the owner of the associated project or the project has a share link."""

    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun, Project)
            .join(Project, col(WorkflowRun.project_id) == col(Project.id))
            .where(col(WorkflowRun.id) == workflow_run_id)
        )
        result = (await session.execute(stmt)).one_or_none()
        if not result:
            raise HTTPException(status_code=404, detail="Workflow run not found")

        workflow_run, project = result.tuple()

        share_link_stmt = select(ShareLink).where(
            col(ShareLink.resource_type) == "project",
            col(ShareLink.resource_id) == workflow_run.project_id,
            col(ShareLink.is_active) == True,
        )
        share_link = (await session.execute(share_link_stmt)).scalar_one_or_none()

        return share_link is not None or (
            user is not None and project.user_id == user.id
        )
