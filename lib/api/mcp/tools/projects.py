import json

from fastmcp.dependencies import CurrentContext
from fastmcp.server.auth import AccessToken
from fastmcp.server.context import Context
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers, serialization
from lib.api.mcp.instance import mcp
from lib.models.file import FileRole
from lib.services.file_finalization import finalize_file
from lib.services import project_content
from lib.services.projects import create_project as create_project_record
from lib.services.projects import get_project_access, get_user_projects


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
    include_document: bool = False,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Get a project's status and detected issues by project ID.

    Returns project metadata, the latest run of each workflow type (status and
    the errors it recorded, without its full state), the detected issues,
    reference_count, and a project_url link to view the project in the web UI.

    For more than the summary:
    - get_project_references: the extracted references (and their IDs), the
      supporting files matched to them, and the web fetch outcomes.
    - get_workflow_run: one run's full state, for results a workflow reports
      outside of issues.
    - list_project_files: the project's files.

    revision: optional revision number to fetch. Defaults to the latest revision.
    Use list_revisions to see all available revisions.
    include_document: also return the main document's markdown, title and
    authors under `document`. Off by default, since it can be long.
    """

    user = await helpers.resolve_user(token)
    return await serialization.get_project_summary_json(
        project_id, user, revision=revision, include_document=include_document
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
    Use get_project with a project_id to fetch a specific project's status and issues.
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


@mcp.tool(
    annotations=ToolAnnotations(
        destructive_hint=False,
        idempotent_hint=True,
        read_only_hint=True,
        open_world_hint=False,
    )
)
async def get_project_references(
    project_id: str,
    revision: int | None = None,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """
    Get the references extracted from a project's main document.

    Returns JSON with:
    - extracted_references: each reference with its `id` and text. Pass the
      `id` as reference_id to get_tus_upload_credentials to upload a
      supporting file for that reference.
    - matches: the supporting files matched to each reference.
    - fetched_references: the outcome of fetching each reference from the web
      (only after reference_downloader ran).

    All three are empty until reference_extraction has run.

    revision: optional revision number. Defaults to the latest revision.
    """
    user = await helpers.resolve_user(token)
    project, _ = await get_project_access(project_id, user=user)
    resolved_revision = revision if revision is not None else project.current_revision
    references = await project_content.get_project_references(
        str(project.id), resolved_revision
    )
    return references.model_dump_json()
