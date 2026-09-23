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
        destructive_hint=False,
        idempotent_hint=False,
        read_only_hint=False,
        open_world_hint=False,
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
    analysis workflows (e.g. document_processing, reference_extraction).

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
        destructive_hint=False,
        idempotent_hint=True,
        read_only_hint=True,
        open_world_hint=False,
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
        destructive_hint=False,
        idempotent_hint=True,
        read_only_hint=True,
        open_world_hint=False,
    )
)
async def list_projects(
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    List projects belonging to the authenticated user, newest activity first.

    Returns a JSON object with `total` (projects matching overall) and `items`,
    an array of objects each with project_id, title, and project_url.

    search: optional text; only projects whose title contains every term are returned.
    limit: page size, at most 200. offset: number of projects to skip. When
    offset + len(items) < total there are more pages to fetch.
    Use get_project with a project_id to fetch full details for a specific project.
    """
    user = await helpers.resolve_user(token)
    page = await get_user_projects(user, search=search, limit=limit, offset=offset)
    return json.dumps(
        {
            "total": page.total,
            "items": [
                {
                    "project_id": str(item.project.id),
                    "title": item.project.title,
                    "project_url": helpers.build_project_url(str(item.project.id)),
                }
                for item in page.items
            ],
        }
    )
