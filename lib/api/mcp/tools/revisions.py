import json
import uuid

from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers
from lib.api.mcp.instance import mcp
from lib.models.file import FileRole
from lib.models.project import AccessLevel
from lib.services.files.finalization import finalize_file
from lib.services.projects.revisions import list_project_revisions
from lib.services.projects.service import create_new_revision, get_project_access


@mcp.tool(
    annotations=ToolAnnotations(
        destructive_hint=False,
        idempotent_hint=False,
        read_only_hint=False,
        open_world_hint=False,
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

    This cancels any running workflows of the current revision and increments the
    revision counter; earlier revisions keep their issues.

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
    user = await helpers.resolve_user(token)
    new_revision, previous_types = await create_new_revision(project_id, user)

    result: dict = {
        "revision": new_revision,
        "previous_workflow_types": [str(t) for t in previous_types],
        "project_url": helpers.build_project_url(project_id),
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
        destructive_hint=False,
        idempotent_hint=True,
        read_only_hint=True,
        open_world_hint=False,
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
    fetch the results for any revision.
    """
    user = await helpers.resolve_user(token)
    project, _ = await get_project_access(
        project_id, user=user, required_level=AccessLevel.READ
    )

    return json.dumps(
        [
            {
                "revision": item.revision,
                "is_current": item.revision == project.current_revision,
                "main_file_name": item.main_file_name,
                "main_file_id": item.main_file_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in await list_project_revisions(project)
        ]
    )
