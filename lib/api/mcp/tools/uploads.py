import json

from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken
from mcp.types import ToolAnnotations

from lib.api.mcp import helpers
from lib.api.mcp.instance import mcp
from lib.models.project import AccessLevel
from lib.services.projects import get_project_access


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
    user = await helpers.resolve_user(token)
    await get_project_access(project_id, user=user, required_level=AccessLevel.WRITE)

    bearer_token, expires_in_seconds = helpers.mint_tus_bearer_token(user)

    resolved_role = role if role in ("main", "support") else "support"

    required_metadata: dict[str, str | None] = {
        "project_id": project_id,
        "reference_id": reference_id if resolved_role == "support" else None,
        "role": resolved_role,
    }

    return json.dumps(
        {
            "tus_url": helpers.build_tus_url(),
            "bearer_token": bearer_token,
            "expires_in_seconds": expires_in_seconds,
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
