import json
import uuid
from datetime import datetime, timedelta, timezone

import aiofiles
import jwt as pyjwt
from fastmcp import FastMCP
from fastmcp.dependencies import CurrentContext
from fastmcp.server.auth import AccessToken
from fastmcp.server.context import Context
from fastmcp.server.dependencies import CurrentAccessToken
from fastmcp.utilities.types import File
from mcp.server.fastmcp import Icon
from mcp.types import ToolAnnotations

from lib.api.mcp_auth import create_mcp_auth
from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_runner import (
    WorkflowGateRequiredError,
    run_multiple_workflows_blocking,
)
from lib.config.env import config as env_config
from lib.models.file import File as FileModel, FileRole
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.docx_workflow_service import DocxManipulatorType, generate_docx
from lib.services.file_finalization import finalize_file
from lib.services.files import get_files_by_project_id
from lib.services.projects import create_project as create_project_record
from lib.services.projects import (
    create_new_revision,
    delete_project_file_with_cleanup,
    get_project_access,
    get_project_detailed_from_project,
    get_user_projects,
)
from lib.services.files import get_project_files_list_items
from lib.services.references import get_file_reference_matches
from lib.services.users import get_or_create_user_by_email
from lib.services.workflow_types import get_workflow_types_for_user
from lib.workflows.models import SeverityEnum, WorkflowRunType

mcp_auth = create_mcp_auth()
mcp = FastMCP(
    "AI Reviewer / Draft Detective",
    auth=mcp_auth,
    website_url=env_config.FRONTEND_URL,
    icons=[Icon(src=env_config.FRONTEND_URL + "/icon.svg")],
)


def _looks_like_email(value: str) -> bool:
    """Minimal check: contains exactly one '@' with text on both sides."""
    parts = value.split("@")
    return len(parts) == 2 and all(parts)


async def _resolve_user(token: AccessToken) -> User:
    """Resolve the DB user from an authenticated OAuth access token."""
    claims = token.claims
    upstream = claims.get("upstream_claims", {})
    # Azure Entra ID: email is optional and preferred_username (UPN) may be
    # the only identifier.  FastMCP validates the upstream Azure JWT and
    # exposes its claims at the top level, but also embeds them under
    # "upstream_claims" in its own reference JWT — check both paths.
    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or upstream.get("email")
        or upstream.get("preferred_username")
    )
    name = claims.get("name") or upstream.get("name") or email
    if not email:
        raise RuntimeError("Token missing 'email' claim")
    if not _looks_like_email(email):
        raise RuntimeError(f"Resolved identity '{email}' is not a valid email address")
    return await get_or_create_user_by_email(email=email, name=name)


def _build_project_url(project_id: str) -> str:
    base = env_config.FRONTEND_URL.rstrip("/")
    return f"{base}/projects/{project_id}"


def _build_settings_url() -> str:
    return f"{env_config.FRONTEND_URL.rstrip('/')}/account"


def _require_api_key(user: User) -> None:
    """Raise a clear error when no OpenAI API key is available."""
    if user.encrypted_openai_api_key or env_config.OPENAI_API_KEY:
        return
    settings_url = _build_settings_url()
    raise ValueError(
        f"Your account ({user.email}) does not have an OpenAI API key configured on Draft Detective. "
        "This is a one-time setup: open the link below, sign in with the same account, "
        "and save your key. It will be encrypted and tied to your account only. "
        f"Once saved, all future MCP requests will pick it up automatically.\n\n"
        f"Settings page: {settings_url}"
    )


async def _get_project_details_json(
    project_id: str,
    access_level: AccessLevel,
    user: User,
    revision: int | None = None,
) -> str:
    """Fetch project details and return as JSON, excluding files and feedbacks."""
    project, _ = await get_project_access(
        project_id, user=user, required_level=access_level
    )
    project_detailed = await get_project_detailed_from_project(
        project=project,
        access_level=access_level,
        include_internal=True,
        revision=revision,
    )
    data = project_detailed.model_dump(mode="json", exclude={"files", "feedbacks"})
    data["project_url"] = _build_project_url(project_id)
    return json.dumps(data)


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
    )
)
async def list_workflow_types(token: AccessToken = CurrentAccessToken()) -> str:
    """
    Lists all available workflow / analysis types that can be run on a project / document,
    along with the ordered category display config.

    workflow_types: flat list of all workflows with type identifier (used when starting a
    workflow), display name, description, and dependency information.
    categories: ordered list of categories, each with an ordered list of workflow type slugs
    that belong to it — use this to understand grouping and display order.
    """
    user = await _resolve_user(token)
    return get_workflow_types_for_user(user).model_dump_json()


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=False,
        readOnlyHint=False,
        openWorldHint=False,
    )
)
async def create_project(
    title: str,
    content_markdown: str | None = None,
    ctx: Context = CurrentContext(),
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Create a NEW project and optionally ingest a markdown document.

    Only use this for a brand-new document that has never been analyzed before.
    If you are re-analyzing an updated version of an existing document (e.g. after
    fixing issues), do NOT create a new project — use create_revision on the
    existing project instead. This preserves history and lets the user compare
    revisions.

    content_markdown: the document content as markdown. For small/medium documents,
        pass the content directly here. For large files or non-markdown formats
        (PDF, DOCX), omit this and use get_tus_upload_credentials with role="main"
        to upload the file after project creation.

    After creation, use run_workflow with the returned project_id to start
    analysis workflows (e.g. document_processing, claim_extraction).

    Returns JSON with project_id, file_id (if content was provided), and project_url.
    """
    user = await _resolve_user(token)

    project = await create_project_record(title=title, user=user)

    result: dict = {
        "project_id": str(project.id),
        "project_url": _build_project_url(str(project.id)),
    }

    if content_markdown is not None:
        file_record = await finalize_file(
            content=content_markdown.encode("utf-8"),
            filename="document.md",
            project_id=project.id,
            user_id=user.id,
            role=FileRole.MAIN,
            revision=1,
        )
        result["file_id"] = str(file_record.id)
    else:
        result["next_step"] = (
            "Upload the main document using get_tus_upload_credentials with role='main'"
        )

    return json.dumps(result)


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

    user = await _resolve_user(token)
    _require_api_key(user)

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
        return json.dumps(_build_gate_required_payload(exc))

    return await _get_project_details_json(project_id, AccessLevel.WRITE, user)


def _build_gate_required_payload(exc: WorkflowGateRequiredError) -> dict:
    """Build the JSON payload returned to the MCP client when consent is missing."""
    pending_human_approval = [w.value for w in exc.pending_human_approval]
    pending_web_search = [w.value for w in exc.pending_web_search]

    retry_flags: list[str] = []
    if pending_human_approval:
        retry_flags.append("approve_human_steps=true")
    if pending_web_search:
        retry_flags.append("approve_web_search=true")
    retry_flags_text = " and ".join(retry_flags)

    sections: list[str] = []
    if pending_human_approval:
        sections.append(
            "Human approval is required because the user must review the "
            "reference→file mappings before these workflows can run: "
            f"{pending_human_approval}. Share the project_url with the user "
            "so they can review references in the web UI, or offer to list "
            "the references and supporting-file mappings here (use "
            "get_project to fetch them).\n\n"
            "Offer the user these options for filling in missing supporting "
            "files before approving:\n"
            "  1. Have Draft Detective auto-fetch them from the web — add "
            "'reference_downloader' to workflow_types on the retry call "
            "(this also requires approve_web_search=true).\n"
            "  2. Provide/upload the files yourself — call "
            "get_tus_upload_credentials with role='support' and the matching "
            "reference_id (from get_project) for each file, then upload via "
            "the returned TUS endpoint before retrying."
        )
    if pending_web_search:
        sections.append(
            "Web-search consent is required because these workflows access "
            f"the open web: {pending_web_search}. Confirm with the user that "
            "they're OK with Draft Detective making external web requests on "
            "their behalf for this project before retrying."
        )
    sections.append(
        "Once the user confirms (e.g. 'go ahead and start'), call "
        f"run_workflow again with the same arguments plus {retry_flags_text}."
    )

    return {
        "status": "approval_required",
        "project_id": exc.project_id,
        "project_url": _build_project_url(exc.project_id),
        "pending_human_approval": pending_human_approval,
        "pending_web_search": pending_web_search,
        "message": "\n\n".join(sections),
    }


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
    )
)
async def get_project(
    project_id: str,
    revision: int | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Get full project details by project ID.

    Returns project metadata, workflow results, detected issues, and a
    project_url link to view the project in the web UI.

    revision: optional revision number to fetch. Defaults to the latest revision.
    Use list_revisions to see all available revisions.
    """

    user = await _resolve_user(token)
    return await _get_project_details_json(
        project_id, AccessLevel.READ, user, revision=revision
    )


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
    )
)
async def list_projects(token: AccessToken = CurrentAccessToken()) -> str:
    """
    List all projects belonging to the authenticated user.

    Returns a JSON array of objects, each with project_id, title, and project_url.
    Use get_project with a project_id to fetch full details for a specific project.
    """
    user = await _resolve_user(token)
    projects = await get_user_projects(user)
    return json.dumps(
        [
            {
                "project_id": str(item.project.id),
                "title": item.project.title,
                "project_url": _build_project_url(str(item.project.id)),
            }
            for item in projects
        ]
    )


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
    )
)
async def export_project_docx(
    project_id: str,
    workflow_types: list[WorkflowRunType] | None = None,
    severities: list[SeverityEnum] | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> File:
    """
    Export a project's analysis results as a reviewed .docx file.

    The returned file is the original document with AI-generated review comments
    inserted inline — one comment per detected issue. Open it in Word or Google
    Docs to read the full review.

    The project must have been analysed first (run_workflow must have completed).
    Only works when the project's main document is a .docx or .doc file.

    workflow_types: optional list of workflow types to include. Defaults to all
        workflow types. Use list_workflow_types to see available values.

    severities: optional list of severity levels to include. Defaults to all
        non-passing severities (low, medium, high).
    """
    user = await _resolve_user(token)
    await get_project_access(project_id, user=user, required_level=AccessLevel.READ)

    file_path, filename = await generate_docx(
        project_id=project_id,
        share_token=None,
        workflow_types=workflow_types,
        severities=severities,
        docx_type=DocxManipulatorType.COMMENTS,
    )

    async with aiofiles.open(file_path, "rb") as f:
        docx_bytes = await f.read()

    return File(data=docx_bytes, format="docx", name=filename)


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
    )
)
async def list_project_files(
    project_id: str,
    revision: int | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    List files for a project and their reference associations.

    Returns a JSON array where each entry contains:
      file_id, file_name, file_size, file_type, role, revision, reference_id (null if unmatched).

    revision: optional revision number. Defaults to the latest revision.
    Returns the revision's MAIN file plus all shared supporting files.

    Use get_project to retrieve available reference IDs from the workflow state
    (look inside workflow_runs for type "reference_extraction" → state.extracted_references).
    """
    user = await _resolve_user(token)
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.READ
    )

    resolved_revision = revision if revision is not None else project.current_revision
    files = await get_project_files_list_items(project.id, revision=resolved_revision)
    matches = await get_file_reference_matches(project_id, revision=resolved_revision)
    file_to_reference = {m.file_id: m.reference_id for m in matches}

    return json.dumps(
        [
            {
                "file_id": str(f.id),
                "file_name": f.file_name,
                "file_size": f.file_size,
                "file_type": f.file_type,
                "role": str(f.role) if f.role else None,
                "revision": f.revision,
                "reference_id": file_to_reference.get(str(f.id)),
            }
            for f in files
        ]
    )


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True,
        idempotentHint=False,
        readOnlyHint=False,
        openWorldHint=False,
    )
)
async def remove_reference_file(
    project_id: str,
    file_id: str,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Remove a supporting file from a project and clean up its reference association.

    Deletes the file record and its disk content (unless shared with another project),
    then removes any reference-file match that pointed to this file.

    Returns JSON with the deleted file_id and the list of reference IDs that were unlinked.
    Use list_project_files to discover file IDs for a project.
    """
    user = await _resolve_user(token)
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.WRITE
    )

    deleted_count, removed_reference_ids = await delete_project_file_with_cleanup(
        project_id, file_id, revision=project.current_revision
    )
    if deleted_count == 0:
        raise ValueError(f"File {file_id!r} not found in project {project_id!r}")

    return json.dumps(
        {
            "file_id": file_id,
            "removed_from_reference_ids": removed_reference_ids,
        }
    )


def _build_tus_url() -> str:
    """Derive the TUS endpoint URL from MCP_BASE_URL by stripping the /mcp suffix."""
    base = env_config.MCP_BASE_URL
    if base.endswith("/mcp"):
        base = base[: -len("/mcp")]
    return base.rstrip("/") + "/tus"


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=False,
        readOnlyHint=False,
        openWorldHint=False,
    )
)
async def get_tus_upload_credentials(
    project_id: str,
    role: str = "support",
    reference_id: str | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Get credentials and URL to upload a file via the TUS resumable upload protocol.

    Returns a bearer token (valid for 15 minutes) and the TUS endpoint URL. Use any TUS client
    library (e.g. tus-js-client, tuspy) to perform the upload. Start the upload before the token
    expires; in-progress TUS uploads are not interrupted by expiry.

    Steps:
    1. Call this tool with project_id and role.
    2. Create a TUS upload at tus_url with:
       - Header: Authorization: Bearer <bearer_token>
       - TUS metadata fields from required_metadata (include filename for the stored file name)
    3. Upload the file using the TUS protocol (supports chunked / resumable uploads).

    role: "main" for the primary document or "support" for supporting files (default: "support").
        To upload a new main document, first call create_revision, then use role="main".
    reference_id: optional ID of the reference to link the file to (only for supporting files).
        Obtain reference IDs from get_project (workflow_runs → type "reference_extraction" →
        state.extracted_references[].id).
    """
    user = await _resolve_user(token)
    await get_project_access(project_id, user=user, required_level=AccessLevel.WRITE)

    now = datetime.now(timezone.utc)
    payload = {
        "email": user.email,
        "name": user.name,
        "iss": "ai-reviewer",
        "aud": "ai-reviewer-api",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    bearer_token = pyjwt.encode(payload, env_config.AUTH_SECRET, algorithm="HS512")

    resolved_role = role if role in ("main", "support") else "support"

    required_metadata: dict[str, str | None] = {
        "project_id": project_id,
        "reference_id": reference_id if resolved_role == "support" else None,
        "role": resolved_role,
    }

    return json.dumps(
        {
            "tus_url": _build_tus_url(),
            "bearer_token": bearer_token,
            "expires_in_seconds": 900,
            "required_metadata": required_metadata,
            "instructions": (
                "Use any TUS client to upload the file. "
                "The bearer_token is valid for 15 minutes — start the upload before it expires. "
                "Set 'Authorization: Bearer <bearer_token>' on every request. "
                "Pass required_metadata as TUS Upload-Metadata (add a 'filename' field "
                "to control the stored file name). "
                "The upload endpoint supports files up to 500 MB and resumable chunked transfers."
            ),
        }
    )


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=False,
        readOnlyHint=False,
        openWorldHint=False,
    )
)
async def create_revision(
    project_id: str,
    content_markdown: str | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Create a new revision for a project with an updated document.

    Use this instead of create_project when you have an updated version of a document
    that was already analyzed (e.g. after fixing issues found in a previous revision).
    This keeps all history in one project so the user can compare revisions.

    This archives all active issues from the current revision, cancels any running
    workflows, and increments the revision counter.

    content_markdown: the updated document content as markdown. For small/medium
        documents, pass the content directly here and the revision is ready for
        run_workflow immediately. For large files or non-markdown formats (PDF, DOCX),
        omit this and use get_tus_upload_credentials with role="main" to upload
        the file after revision creation.

    After creating the revision (and uploading the document if not passed inline),
    call run_workflow to start analyses. Use previous_workflow_types from the
    response to re-run the same checks, or choose different ones.

    Returns the new revision number, file_id (if content was provided), and the
    list of workflow types that were previously run.
    """
    user = await _resolve_user(token)
    new_revision, previous_types = await create_new_revision(project_id, user)

    result: dict = {
        "revision": new_revision,
        "previous_workflow_types": [str(t) for t in previous_types],
        "project_url": _build_project_url(project_id),
    }

    if content_markdown is not None:
        file_record = await finalize_file(
            content=content_markdown.encode("utf-8"),
            filename="document.md",
            project_id=uuid.UUID(project_id),
            user_id=user.id,
            role=FileRole.MAIN,
            revision=new_revision,
        )
        result["file_id"] = str(file_record.id)
    else:
        result["next_step"] = (
            "Upload the new document using get_tus_upload_credentials with role='main'"
        )

    return json.dumps(result)


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        idempotentHint=True,
        readOnlyHint=True,
        openWorldHint=False,
    )
)
async def list_revisions(
    project_id: str,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    List all revisions for a project.

    Returns a JSON array with each revision's number, main file name, file ID,
    and creation timestamp. Use get_project with a specific revision number to
    fetch detailed results for any revision.
    """
    user = await _resolve_user(token)
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.READ
    )

    main_files = await get_files_by_project_id(project.id, roles=[FileRole.MAIN])
    main_by_revision: dict[int, FileModel] = {}
    for f in main_files:
        if f.revision is not None:
            main_by_revision[f.revision] = f

    revisions = []
    for rev in range(1, project.current_revision + 1):
        main_file = main_by_revision.get(rev)
        revisions.append(
            {
                "revision": rev,
                "is_current": rev == project.current_revision,
                "main_file_name": main_file.file_name if main_file else None,
                "main_file_id": str(main_file.id) if main_file else None,
                "created_at": (
                    main_file.created_at.isoformat()
                    if main_file and main_file.created_at
                    else None
                ),
            }
        )

    return json.dumps(revisions)


mcp_app = mcp.http_app(
    path="/",
    stateless_http=True,  # Stateless mode is needed since production runs multiple instances (workers)
)
