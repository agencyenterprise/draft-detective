"""Who may read a file: whoever may read its project.

Kept apart from `lib.services.files.service` because the central gate,
`get_project_access`, lives in `lib.services.projects.service`, which imports that
module.
"""

import uuid

from fastapi import HTTPException

from lib.config.database import get_async_db_session
from lib.models.file import File
from lib.models.user import User
from lib.services.projects.service import get_project_access
from lib.services.uuid_utils import ensure_uuid


async def check_file_access(file_id: uuid.UUID | str, user: User) -> File:
    """The file, when the signed-in user may read its project.

    Raises:
        HTTPException: 400 for a malformed id, 404 for an unknown file or one that
            belongs to no project, 403 when the project is not readable.
    """
    return await _readable_file(file_id, user=user)


async def check_file_access_by_share_token(
    file_id: uuid.UUID | str, share_token: str
) -> File:
    """The file, when the share token is an active link to its project.

    Raises:
        HTTPException: as `check_file_access`.
    """
    return await _readable_file(file_id, share_token=share_token)


async def _readable_file(
    file_id: uuid.UUID | str,
    user: User | None = None,
    share_token: str | None = None,
) -> File:
    file_uuid = ensure_uuid(file_id, "file ID")
    async with get_async_db_session() as session:
        file = await session.get(File, file_uuid)

    # A conversation's image has no project, so no one may read it here.
    if file is None or file.project_id is None:
        raise HTTPException(status_code=404, detail="File not found")

    await get_project_access(str(file.project_id), user, share_token)
    return file
