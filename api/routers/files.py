import os
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from api.auth import get_current_user
from lib.config.env import config
from lib.models.user import User
from lib.services.files import check_file_access

router = APIRouter(tags=["files"])


@router.get("/api/files/download/{file_id}")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Download a file by ID with access control.

    This endpoint verifies that the authenticated user has access to the file
    by checking if they own the project that the file belongs to.

    Args:
        file_id: UUID of the file to download
        current_user: Authenticated user from JWT token

    Returns:
        FileResponse with the file contents

    Raises:
        HTTPException: 400 for invalid file ID, 404 if file not found, 403 if access denied
    """
    # Check access and get file record
    file = await check_file_access(file_id, current_user.id)

    # Check if the file path is within the upload mount path do avoid path traversal attacks
    if not file.file_path.startswith(config.FILE_UPLOADS_MOUNT_PATH):
        raise HTTPException(
            status_code=400, detail="File path is not within the upload mount path"
        )

    # Validate file exists before attempting to stream it
    if not os.path.isfile(file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Return the file from the file system
    return FileResponse(
        path=file.file_path,
        media_type=file.file_type,
    )
