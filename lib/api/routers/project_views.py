"""The project page's reads, split so each tab loads only what it shows.

`/overview` is the one the page polls; the rest are fetched on demand. All of
them authorize through `get_project_access`, so a share token works as well as
a signed-in owner. Project CRUD, files, revisions and exports stay in
`projects.py`; this router holds only the reads the project page composes.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from lib.api.auth import get_current_user_optional
from lib.models.issue import Issue
from lib.models.workflow_run import WorkflowRunType
from lib.models.user import User
from lib.services.issue_persistence import get_project_issues
from lib.services.project_content import (
    ProjectDocument,
    ProjectReferences,
    get_project_document,
    get_project_references,
)
from lib.services.project_overview import (
    ProjectOverview,
    WorkflowRunSummary,
    get_project_overview,
    get_workflow_run_summaries_by_type,
)
from lib.services.projects import get_project_access

router = APIRouter(tags=["projects"])

_REVISION_QUERY = Query(
    default=None,
    description="Revision number. Defaults to the project's current revision.",
)
_SHARE_TOKEN_QUERY = Query(
    default=None,
    description="Share token, for viewers reading the project through a share link.",
)


@router.get("/api/project/{project_id}/overview", response_model=ProjectOverview)
async def get_project_overview_endpoint(
    project_id: str,
    revision: Optional[int] = _REVISION_QUERY,
    share_token: Optional[str] = _SHARE_TOKEN_QUERY,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """The project with each run's status and errors, its files and counts. No run states."""
    project, access_level = await get_project_access(
        project_id, current_user, share_token
    )
    return await get_project_overview(project, access_level, revision=revision)


@router.get("/api/project/{project_id}/document", response_model=ProjectDocument)
async def get_project_document_endpoint(
    project_id: str,
    revision: Optional[int] = _REVISION_QUERY,
    share_token: Optional[str] = _SHARE_TOKEN_QUERY,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """The main document's markdown, title and authors for a revision."""
    project, _ = await get_project_access(project_id, current_user, share_token)
    resolved_revision = revision if revision is not None else project.current_revision
    return await get_project_document(str(project.id), resolved_revision)


@router.get("/api/project/{project_id}/issues", response_model=List[Issue])
async def get_project_issues_endpoint(
    project_id: str,
    revision: Optional[int] = _REVISION_QUERY,
    share_token: Optional[str] = _SHARE_TOKEN_QUERY,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """The persisted issues of a project revision, archived ones excluded."""
    project, _ = await get_project_access(project_id, current_user, share_token)
    resolved_revision = revision if revision is not None else project.current_revision
    return list(
        await get_project_issues(uuid.UUID(str(project.id)), revision=resolved_revision)
    )


@router.get("/api/project/{project_id}/references", response_model=ProjectReferences)
async def get_project_references_endpoint(
    project_id: str,
    revision: Optional[int] = _REVISION_QUERY,
    share_token: Optional[str] = _SHARE_TOKEN_QUERY,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Extracted references, their file matches and web fetch outcomes."""
    project, _ = await get_project_access(project_id, current_user, share_token)
    resolved_revision = revision if revision is not None else project.current_revision
    return await get_project_references(str(project.id), resolved_revision)


@router.get(
    "/api/project/{project_id}/workflow-runs",
    response_model=List[WorkflowRunSummary],
)
async def get_project_workflow_runs_by_type_endpoint(
    project_id: str,
    workflow_type: WorkflowRunType = Query(
        ...,
        description="The workflow type to filter runs by",
    ),
    revision: Optional[int] = _REVISION_QUERY,
    share_token: Optional[str] = _SHARE_TOKEN_QUERY,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get all workflow runs of a specific type for a project revision, newest first.

    Summaries only (status and the run's own errors), for the run history; a
    run's state comes from `GET /api/workflows/{workflow_run_id}`.
    """

    project, _ = await get_project_access(project_id, current_user, share_token)
    resolved_revision = revision if revision is not None else project.current_revision
    return await get_workflow_run_summaries_by_type(
        project_id, workflow_type, revision=resolved_revision
    )
