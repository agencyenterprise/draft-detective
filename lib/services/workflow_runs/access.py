"""Authorize a caller for one workflow run, through its project's access gate.

A run carries no permissions of its own: whoever may reach its project at the
required level may reach the run. This keeps that rule in `get_project_access`
instead of a second ownership check per caller.
"""

from fastapi import HTTPException

from lib.models.project import AccessLevel
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.projects.service import get_project_access
from lib.services.workflow_runs.service import get_workflow_run


async def get_accessible_workflow_run(
    workflow_run_id: str,
    user: User | None,
    share_token: str | None = None,
    required_level: AccessLevel = AccessLevel.READ,
) -> WorkflowRun:
    """The run's metadata, once the caller holds `required_level` on its project.

    `state_json` stays deferred: callers that need it load it after this check,
    so a refused caller never pays for a multi-MB read.

    Raises:
        HTTPException: 404 if the run is missing or has no project (nobody owns
            it, so nobody is told it exists), else whatever the gate raises.
    """
    run = await get_workflow_run(workflow_run_id)
    if run.project_id is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    await get_project_access(str(run.project_id), user, share_token, required_level)
    return run
