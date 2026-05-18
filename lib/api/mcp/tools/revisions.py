import json
import uuid

from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers
from lib.api.mcp.instance import mcp
from lib.models.file import File as FileModel, FileRole
from lib.models.project import AccessLevel
from lib.services.file_finalization import finalize_file
from lib.services.files import get_files_by_project_id
from lib.services.projects import create_new_revision, get_project_access


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
    user = await helpers.resolve_user(token)
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
