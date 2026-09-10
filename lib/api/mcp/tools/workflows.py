import asyncio
import json
import logging
import time

from fastmcp.dependencies import CurrentContext
from fastmcp.server.auth import AccessToken
from fastmcp.server.context import Context
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers, serialization
from lib.api.mcp.instance import mcp
from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_runner import (
    WorkflowGateRequiredError,
    run_multiple_workflows_blocking,
)
from lib.models.project import AccessLevel
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.projects import get_project_access
from lib.services.workflow_runs import get_project_run_summaries
from lib.workflows.models import WorkflowRunType

logger = logging.getLogger(__name__)

# How often a blocking run_workflow call sends an MCP progress notification.
# Clients abort a call that stays silent too long (Claude Code: 5 minutes for
# remote servers); a progress notification resets that idle clock.
PROGRESS_INTERVAL_SECONDS = 30.0


def _parse_workflow_types(workflow_types: list[str]) -> list[WorkflowRunType]:
    parsed: list[WorkflowRunType] = []
    for wt in workflow_types:
        try:
            parsed.append(WorkflowRunType(wt))
        except ValueError:
            valid = [t.value for t in WorkflowRunType]
            raise ValueError(f"Unknown workflow_type '{wt}'. Valid values: {valid}")
    return parsed


async def _report_batch_progress(
    ctx: Context, project_id: str, revision: int, started_at: float
) -> None:
    """One progress notification describing the revision's runs right now."""
    try:
        runs = await get_project_run_summaries(project_id, revision)
        settled = [
            r
            for r in runs
            if r.status not in (WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING)
        ]
        # WorkflowRun.type is a String column and comes back as a plain str.
        running = [str(r.type) for r in runs if r.status == WorkflowRunStatus.RUNNING]
        elapsed = int(time.monotonic() - started_at)
        await ctx.report_progress(
            progress=len(settled),
            total=len(runs) or None,
            message=f"{elapsed}s elapsed; running: {running or 'none yet'}",
        )
    except Exception as exc:  # progress is best-effort; never fail the call
        logger.warning("run_workflow progress report failed: %s", exc)


async def _run_with_progress(
    ctx: Context, project_id: str, revision: int, runner: asyncio.Task
) -> None:
    """Await the blocking batch while emitting periodic progress notifications."""
    started_at = time.monotonic()
    while True:
        done, _ = await asyncio.wait({runner}, timeout=PROGRESS_INTERVAL_SECONDS)
        if done:
            return
        await _report_batch_progress(ctx, project_id, revision, started_at)


@mcp.tool(
    task=True,
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=False,
        readOnlyHint=False,
        openWorldHint=True,
    ),
)
async def run_workflow(
    project_id: str,
    workflow_types: list[str],
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
    ctx: Context = CurrentContext(),
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Run one or more workflow analyses on a project and block until all complete.

    Required dependencies are automatically resolved and run first in the correct
    order, so there is no need to include dependencies in workflow_types explicitly.

    A project with an uploaded document is required before running any workflow.
    Use create_project first to create a project and ingest a document, then pass
    the returned project_id here. Workflows always run against the project's
    current revision.

    workflow_types must be a list of type values returned by list_workflow_types
    (e.g. ["reference_validation_v2", "recommendation_check"]).

    A full analysis can take several minutes. Progress notifications are sent
    while the call runs so clients that watch for them do not treat it as idle.

    Two kinds of consent gates may apply:

    1. Human approval — some workflows (e.g. claim_reference_validation_v2)
       gate on a human review of the reference→file mappings before running.
    2. Web-search consent — some workflows (e.g. reference_validation_v2,
       reference_downloader, literature_review_v2) call out to the open web,
       which the user must explicitly opt into.

    On the first call, leave both flags at False (the default). When a gate
    applies, the tool returns a JSON response with status="approval_required"
    listing pending_human_approval, pending_web_search, and
    retry_workflow_types, and pointing the user at the project URL. The two
    gates are checked at different moments:

    - Web-search consent is checked up front. If any requested workflow needs
      it, NOTHING is started and the response says so; ask the user before
      anything runs on their document.
    - Human approval is checked mid-flight. Every ungated workflow runs to
      completion first (so the references exist to review), the gated one is
      parked in awaiting_approval, and the response lists only that one.

    After the user explicitly confirms (e.g. "go ahead and start"), call this
    tool again with workflow_types=retry_workflow_types plus
    approve_human_steps=True and/or approve_web_search=True (whichever gates
    were listed). Always pass exactly retry_workflow_types on the retry: every
    type listed explicitly is run again even if it already completed, which
    duplicates its issues and doubles cost and wait time. Human approval is
    recorded per project revision, so once given it is not asked again until
    a new revision is created.

    When the human-approval gate triggers, also offer the user two options
    for filling in missing supporting files:
      1. Have Draft Detective auto-fetch them from the web — include
         "reference_downloader" in workflow_types on the retry call (this
         requires approve_web_search=True).
      2. Provide/upload the files directly — use get_tus_upload_credentials
         with role="support" and the matching reference_id (look it up via
         get_project) for each file, upload, then retry.

    Returns full project details including all workflow results, detected issues,
    and a project_url link to view the project in the web UI.

    Tip: after fixing issues and uploading a new document via create_revision,
    call this again with the same workflow_types to re-analyze the updated document.
    """
    parsed_types = _parse_workflow_types(workflow_types)

    user = await helpers.resolve_user(token)
    helpers.require_api_key(user)

    request = StartMultipleWorkflowsRequest(
        project_id=project_id,
        workflow_types=parsed_types,
    )

    try:
        project, _ = await get_project_access(
            project_id, user=user, required_level=AccessLevel.WRITE
        )
        runner = asyncio.ensure_future(
            run_multiple_workflows_blocking(
                parsed_types,
                request,
                user,
                approve_human_steps=approve_human_steps,
                approve_web_search=approve_web_search,
            )
        )
        await _run_with_progress(ctx, project_id, project.current_revision, runner)
        await runner  # re-raise anything the batch raised
    except WorkflowGateRequiredError as exc:
        return json.dumps(serialization.build_gate_required_payload(exc))

    return await serialization.get_project_details_json(
        project_id, AccessLevel.WRITE, user
    )
