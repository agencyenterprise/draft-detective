from typing import Optional

from fastapi import HTTPException

from lib.config.database import get_db
from lib.models.project import Project
from lib.models.share_link import ShareLink
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun


def has_access_to_workflow_run(user: Optional[User], workflow_run_id: str) -> bool:
    """Check if a user has access to a workflow run, either by being the owner of the associated project or the project has a share link."""

    with get_db() as db:
        result = (
            db.query(WorkflowRun, Project)
            .join(Project, WorkflowRun.project_id == Project.id)
            .filter(WorkflowRun.id == workflow_run_id)
            .first()
        )
        if not result:
            raise HTTPException(status_code=404, detail="Workflow run not found")

        workflow_run, project = result

        share_link = (
            db.query(ShareLink)
            .filter(
                ShareLink.resource_type == "project",
                ShareLink.resource_id == workflow_run.project_id,
                ShareLink.is_active == True,
            )
            .first()
        )

        return share_link is not None or (
            user is not None and project.user_id == user.id
        )
