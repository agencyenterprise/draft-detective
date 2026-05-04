import json

from fastmcp.server.auth import AccessToken
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
from lib.workflows.models import WorkflowRunType


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
    (e.g. ["claim_extraction", "reference_validation"]).

    Two kinds of consent gates may apply:

    1. Human approval — some workflows (e.g. claim_reference_validation_v2)
       gate on a human review of the reference→file mappings before running.
    2. Web-search consent — some workflows (e.g. reference_validation,
       reference_downloader, literature_review) call out to the open web,
       which the user must explicitly opt into.

    On the first call, leave both flags at False (the default). If any gate
    applies, the tool returns a JSON response with status="approval_required"
    listing pending_human_approval and pending_web_search workflow types and
    pointing the user at the project URL. After the user explicitly confirms
    (e.g. "go ahead and start"), call this tool again with the same arguments
    plus approve_human_steps=True and/or approve_web_search=True (whichever
    gates were listed) to record consent and run the workflow.

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
    parsed_types: list[WorkflowRunType] = []
    for wt in workflow_types:
        try:
            parsed_types.append(WorkflowRunType(wt))
        except ValueError:
            valid = [t.value for t in WorkflowRunType]
            raise ValueError(f"Unknown workflow_type '{wt}'. Valid values: {valid}")

    user = await helpers.resolve_user(token)
    helpers.require_api_key(user)

    request = StartMultipleWorkflowsRequest(
        project_id=project_id,
        workflow_types=parsed_types,
    )

    try:
        await run_multiple_workflows_blocking(
            parsed_types,
            request,
            user,
            approve_human_steps=approve_human_steps,
            approve_web_search=approve_web_search,
        )
    except WorkflowGateRequiredError as exc:
        return json.dumps(serialization.build_gate_required_payload(exc))

    return await serialization.get_project_details_json(
        project_id, AccessLevel.WRITE, user
    )
