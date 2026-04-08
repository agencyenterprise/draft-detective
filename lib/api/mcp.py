import json

import aiofiles
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
from lib.services.projects import create_project as create_project_record
from lib.services.projects import get_project_access, get_project_detailed_from_project, get_user_projects
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


mcp_app = mcp.http_app(
    path="/",
    stateless_http=True,  # Stateless mode is needed since production runs multiple instances (workers)
)
