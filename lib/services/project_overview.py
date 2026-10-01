"""The project page's always-loaded payload: what the chrome needs, no states.

`ProjectDetailed` hands back every run's full hydrated state, which reaches
several MB on a fully analysed project and was re-sent on every 3s poll. The
overview carries only what the tabs, badges and banners read, and pulls the
few state fields it needs (each run's errors, the reference count, the main
file's path) out of `state_json` in SQL, so no state is shipped or hydrated.
Everything heavier has its own endpoint, fetched when a tab needs it.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import case, func, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import FileListItem
from lib.models.issue import Issue, IssueStatus
from lib.models.project import AccessLevel, Project
from lib.models.workflow_run import WorkflowRun, WorkflowRunPublic
from lib.services.files import get_project_files_list_items
from lib.services.share_links import ShareStatusResponse, get_share_status
from lib.services.workflow_runs import latest_run_per_type_stmt
from lib.workflows.models import WorkflowError, WorkflowRunType
from lib.workflows.registry import (
    available_workflow_type_values,
    is_available_workflow_type,
)

logger = logging.getLogger(__name__)

_STATE = col(WorkflowRun.state_json)
_DOCX_EXTENSIONS = (".docx", ".doc")


class WorkflowRunSummary(BaseModel):
    """A run without its state: enough to show its status anywhere on the page."""

    run: WorkflowRunPublic
    errors: List[WorkflowError] = Field(
        default_factory=list,
        description="Errors recorded by this run itself (earlier runs' errors excluded)",
    )


class ProjectOverview(BaseModel):
    project: Project
    access_level: AccessLevel = Field(
        description="The access level of the current user for this project",
    )
    revision: int = Field(description="The revision being returned")
    workflow_runs: List[WorkflowRunSummary] = Field(
        default_factory=list,
        description="The most relevant run per workflow type for the revision",
    )
    files: List[FileListItem] = Field(
        default_factory=list,
        description="The project's files across every revision",
    )
    reference_count: int = Field(
        default=0,
        description="How many references reference extraction found in the main document",
    )
    has_docx: bool = Field(
        default=False,
        description="Whether the processed main document is a Word file",
    )
    issues_version: str = Field(
        description=(
            "Changes whenever the revision's issues do. Clients key their issues "
            "fetch on it so they only refetch when there is something new."
        ),
    )
    share_status: Optional[ShareStatusResponse] = Field(
        default=None,
        description=(
            "Whether the project has a public link, and the link. Only for the "
            "owner (WRITE access); null for share-link viewers and admins."
        ),
    )


def _json_array_length(expr: Any) -> Any:
    """Length of a JSONB array, or NULL for anything that is not one."""
    return case(
        (func.jsonb_typeof(expr) == "array", func.jsonb_array_length(expr)),
        else_=None,
    )


def current_run_errors(run_id: uuid.UUID, raw_errors: Any) -> List[WorkflowError]:
    """The persisted errors that belong to this run, skipping unreadable ones.

    A state's `errors` list accumulates across re-runs on the same thread, so
    only the entries stamped with this run's id are its own.
    """
    if not isinstance(raw_errors, list):
        return []
    errors: List[WorkflowError] = []
    for raw in raw_errors:
        try:
            error = WorkflowError.model_validate(raw)
        except ValidationError:
            continue
        if error.workflow_run_id == str(run_id):
            errors.append(error)
    return errors


def _summary(run: WorkflowRun, raw_errors: Any) -> WorkflowRunSummary:
    return WorkflowRunSummary(
        run=WorkflowRunPublic.model_validate(run),
        errors=current_run_errors(run.id, raw_errors),
    )


class _OverviewRuns(BaseModel):
    summaries: List[WorkflowRunSummary]
    reference_count: int = 0
    has_docx: bool = False


async def _overview_runs(project_id: str, revision: int) -> _OverviewRuns:
    stmt = (
        latest_run_per_type_stmt(project_id, revision)
        .add_columns(
            _STATE["errors"].label("errors"),
            _json_array_length(_STATE["extracted_references"]).label("ref_count"),
            _STATE["file"]["file_path"].astext.label("main_file_path"),
        )
        .order_by(col(WorkflowRun.created_at).asc())
    )
    async with get_async_db_session() as session:
        rows = (await session.execute(stmt)).all()

    result = _OverviewRuns(summaries=[])
    for run, raw_errors, ref_count, main_file_path in rows:
        # A run whose workflow no longer has a manifest is never surfaced.
        if not is_available_workflow_type(run.type):
            continue
        result.summaries.append(_summary(run, raw_errors))
        if run.type == WorkflowRunType.REFERENCE_EXTRACTION:
            result.reference_count = ref_count or 0
        elif run.type == WorkflowRunType.DOCUMENT_PROCESSING and main_file_path:
            result.has_docx = main_file_path.lower().endswith(_DOCX_EXTENSIONS)
    return result


async def get_issues_version(project_id: uuid.UUID, revision: int) -> str:
    """A fingerprint of the revision's visible issues: count, latest update, resolved count."""
    stmt = select(
        func.count(),
        func.max(col(Issue.updated_at)),
        func.count(col(Issue.resolved_at)),
    ).where(
        col(Issue.project_id) == project_id,
        col(Issue.revision) == revision,
        col(Issue.status) != IssueStatus.ARCHIVED,
        col(Issue.workflow_type).in_(available_workflow_type_values()),
    )
    async with get_async_db_session() as session:
        count, last_updated, resolved = (await session.execute(stmt)).one()
    stamp = last_updated.isoformat() if isinstance(last_updated, datetime) else ""
    return f"{count}:{resolved}:{stamp}"


async def get_project_overview(
    project: Project,
    access_level: AccessLevel,
    revision: Optional[int] = None,
) -> ProjectOverview:
    """The overview of one revision; defaults to the project's current one."""
    resolved_revision = revision if revision is not None else project.current_revision
    # Runs first, issues after. A finishing run commits its issues before it
    # marks itself completed, so reading in this order means a completed run
    # always comes with an issues_version that includes its findings. Read in
    # parallel, the version could predate them while the status did not, and
    # the client, seeing nothing left to poll for, would keep the old issues.
    runs = await _overview_runs(str(project.id), resolved_revision)
    files, issues_version, share_status = await asyncio.gather(
        get_project_files_list_items(project.id),
        get_issues_version(project.id, resolved_revision),
        _owner_share_status(project, access_level),
    )
    return ProjectOverview(
        project=project,
        access_level=access_level,
        revision=resolved_revision,
        workflow_runs=runs.summaries,
        files=files,
        reference_count=runs.reference_count,
        has_docx=runs.has_docx,
        issues_version=issues_version,
        share_status=share_status,
    )


async def _owner_share_status(
    project: Project, access_level: AccessLevel
) -> Optional[ShareStatusResponse]:
    # Managing the link is the owner's business: the share page itself is
    # served this overview, and admins reading a project were never shown it.
    if access_level != AccessLevel.WRITE:
        return None
    return await get_share_status("project", project.id)


async def get_workflow_run_summaries_by_type(
    project_id: str,
    workflow_type: WorkflowRunType,
    revision: int,
) -> List[WorkflowRunSummary]:
    """Every run of one type on a revision, newest first, without states."""
    stmt = (
        select(WorkflowRun, _STATE["errors"].label("errors"))
        .where(
            col(WorkflowRun.project_id) == project_id,
            col(WorkflowRun.type) == workflow_type,
            col(WorkflowRun.revision) == revision,
        )
        .order_by(col(WorkflowRun.created_at).desc())
    )
    async with get_async_db_session() as session:
        rows = (await session.execute(stmt)).all()
    return [_summary(run, raw_errors) for run, raw_errors in rows]
