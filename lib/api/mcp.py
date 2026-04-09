import json
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
from lib.api.services.workflow_runner import run_multiple_workflows_blocking
from lib.config.env import config as env_config
from lib.models.file import FileRole
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.docx_workflow_service import DocxManipulatorType, get_or_generate_docx
from lib.services.file_finalization import finalize_file
from lib.services.files import delete_project_files, get_files_by_project_id
from lib.services.projects import create_project as create_project_record
from lib.services.projects import (
    get_project_access,
    get_project_detailed_from_project,
    get_user_projects,
)
from lib.services.references import (
    get_file_reference_matches,
    remove_file_from_references,
)
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


async def _resolve_user(token: AccessToken) -> User:
    """Resolve the DB user from an authenticated OAuth access token."""
    email = token.claims.get("email")
    name = token.claims.get("name", email)
    if not email:
        raise RuntimeError("Token missing 'email' claim")
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
    project_id: str, access_level: AccessLevel, user: User
) -> str:
    """Fetch project details and return as JSON, excluding files and feedbacks."""
    project, _ = await get_project_access(
        project_id, user=user, required_level=access_level
    )
    project_detailed = await get_project_detailed_from_project(
        project=project,
        access_level=access_level,
        include_internal=True,
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
    content_markdown: str,
    ctx: Context = CurrentContext(),
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Create a project and ingest a markdown document.

    After creation, use run_workflow with the returned project_id to start
    analysis workflows (e.g. document_processing, claim_extraction).

    Returns JSON with project_id, file_id, and project_url (a link to the
    project in the web UI where the user can see full details).
    """
    user = await _resolve_user(token)

    project = await create_project_record(title=title, user=user)

    file_record = await finalize_file(
        content=content_markdown.encode("utf-8"),
        filename="document.md",
        project_id=project.id,
        user_id=user.id,
        role=FileRole.MAIN,
    )

    return json.dumps(
        {
            "project_id": str(project.id),
            "file_id": str(file_record.id),
            "project_url": _build_project_url(str(project.id)),
        }
    )


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
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Run one or more workflow analyses on a project and block until all complete.

    Required dependencies are automatically resolved and run first in the correct
    order, so there is no need to include dependencies in workflow_types explicitly.

    A project with an uploaded document is required before running any workflow.
    Use create_project first to create a project and ingest a document, then pass
    the returned project_id here.

    workflow_types must be a list of type values returned by list_workflow_types
    (e.g. ["claim_extraction", "reference_validation"]).

    Returns full project details including all workflow results, detected issues,
    and a project_url link to view the project in the web UI.
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

    await run_multiple_workflows_blocking(parsed_types, request, user)

    return await _get_project_details_json(project_id, AccessLevel.WRITE, user)


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
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Get full project details by project ID.

    Returns project metadata, workflow results, detected issues, and a
    project_url link to view the project in the web UI.
    """

    user = await _resolve_user(token)
    return await _get_project_details_json(project_id, AccessLevel.READ, user)


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

    file_path, filename = await get_or_generate_docx(
        project_id=project_id,
        share_token=None,
        workflow_types=workflow_types,
        severities=severities,
        docx_type=DocxManipulatorType.COMMENTS,
        use_cache=True,
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
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    List all files for a project and their reference associations.

    Returns a JSON array where each entry contains:
      file_id, file_name, file_size, file_type, role, reference_id (null if unmatched).

    Use get_project to retrieve available reference IDs from the workflow state
    (look inside workflow_runs for type "reference_extraction" → state.extracted_references).
    """
    user = await _resolve_user(token)
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.READ
    )

    files = await get_files_by_project_id(project.id)
    matches = await get_file_reference_matches(project_id)
    file_to_reference = {m.file_id: m.reference_id for m in matches}

    return json.dumps(
        [
            {
                "file_id": str(f.id),
                "file_name": f.file_name,
                "file_size": f.file_size,
                "file_type": f.file_type,
                "role": str(f.role) if f.role else None,
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

    deleted_count = await delete_project_files(project.id, target_file_ids=[file_id])
    if deleted_count == 0:
        raise ValueError(f"File {file_id!r} not found in project {project_id!r}")

    removed_reference_ids = await remove_file_from_references(project_id, file_id)

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
    reference_id: str | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Get credentials and URL to upload a supporting file via the TUS resumable upload protocol.

    Returns a bearer token (valid for 15 minutes) and the TUS endpoint URL. Use any TUS client
    library (e.g. tus-js-client, tuspy) to perform the upload. Start the upload before the token
    expires; in-progress TUS uploads are not interrupted by expiry.

    Steps:
    1. Call this tool with project_id and optional reference_id.
    2. Create a TUS upload at tus_url with:
       - Header: Authorization: Bearer <bearer_token>
       - TUS metadata fields from required_metadata (include filename for the stored file name)
    3. Upload the file using the TUS protocol (supports chunked / resumable uploads).

    reference_id: optional ID of the reference to link the file to. Obtain reference IDs
        from get_project (workflow_runs → type "reference_extraction" → state.extracted_references[].id).
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

    required_metadata: dict[str, str | None] = {
        "project_id": project_id,
        "reference_id": reference_id,
        "role": "support",
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


mcp_app = mcp.http_app(
    path="/",
    stateless_http=True,  # Stateless mode is needed since production runs multiple instances (workers)
)
