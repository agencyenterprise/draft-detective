import json

import aiofiles
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken
from fastmcp.utilities.types import File
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers
from lib.api.mcp.instance import mcp
from lib.models.project import AccessLevel
from lib.services.docx_workflow_service import DocxManipulatorType, generate_docx
from lib.services.files import (
    get_project_files_list_items,
)
from lib.services.projects import (
    delete_project_file_with_cleanup,
    get_project_access,
)
from lib.services.references import get_file_reference_matches
from lib.workflows.models import SeverityEnum, WorkflowRunType


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
    user = await helpers.resolve_user(token)
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
    user = await helpers.resolve_user(token)
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
    user = await helpers.resolve_user(token)
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
