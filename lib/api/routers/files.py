import os

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import FileResponse

from lib.api.auth import get_current_user_optional
from lib.config.env import config
from lib.models.user import User
from lib.services.files.access import (
    check_file_access,
    check_file_access_by_share_token,
)

router = APIRouter(tags=["files"])

# Types a browser shows without running anything the file carries. A file's
# type comes from its bytes (libmagic on upload, the document for an extracted
# image, the remote server for a downloaded reference), so anything else, HTML
# and SVG above all, is sent as a download: rendered inline through the
# frontend's same-origin proxy, its script would run with the viewer's session.
_INLINE_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "text/plain",
    }
)


@router.get("/api/files/download/{file_id}")
async def download_file(
    file_id: str,
    share_token: str | None = Query(None, description="Share token for public access"),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    Download a file by ID with access control.

    This endpoint supports two access modes:
    1. Authenticated access: User must own the project containing the file
    2. Share token access: Valid share token for the project grants read access

    Args:
        file_id: UUID of the file to download
        share_token: Optional share token for unauthenticated access
        current_user: Authenticated user from JWT token (optional when share_token provided)

    Returns:
        FileResponse with the file contents

    Raises:
        HTTPException: 400 for invalid file ID, 401 if not authenticated, 404 if file not found, 403 if access denied
    """
    # Check access via share token or user authentication
    if share_token:
        file = await check_file_access_by_share_token(file_id, share_token)
    elif current_user:
        file = await check_file_access(file_id, current_user)
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Check if the file path is within the upload mount path do avoid path traversal attacks
    if not file.file_path.startswith(config.FILE_UPLOADS_MOUNT_PATH):
        raise HTTPException(
            status_code=400, detail="File path is not within the upload mount path"
        )

    # Validate file exists before attempting to stream it
    if not os.path.isfile(file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Named after the upload, or the browser names it after the URL (the file's
    # id). Inline, so a PDF or image still opens in the tab the link opens.
    inline = file.file_type in _INLINE_TYPES
    return FileResponse(
        path=file.file_path,
        media_type=file.file_type,
        filename=file.file_name,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )
