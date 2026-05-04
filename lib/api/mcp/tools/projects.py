import json

from fastmcp.dependencies import CurrentContext
from fastmcp.server.auth import AccessToken
from fastmcp.server.context import Context
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers, serialization
from lib.api.mcp.instance import mcp
from lib.models.file import FileRole
from lib.models.project import AccessLevel
from lib.services.file_finalization import finalize_file
from lib.services.projects import create_project as create_project_record
from lib.services.projects import get_user_projects


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
    user = await helpers.resolve_user(token)

    project = await create_project_record(title=title, user=user)

    result: dict = {
        "project_id": str(project.id),
        "project_url": helpers.build_project_url(str(project.id)),
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

    user = await helpers.resolve_user(token)
    return await serialization.get_project_details_json(
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
    user = await helpers.resolve_user(token)
    projects = await get_user_projects(user)
    return json.dumps(
        [
            {
                "project_id": str(item.project.id),
                "title": item.project.title,
                "project_url": helpers.build_project_url(str(item.project.id)),
            }
            for item in projects
        ]
    )
