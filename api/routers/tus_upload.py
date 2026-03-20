"""TUS resumable upload router using tuspyserver."""

import logging
import os
import uuid
from typing import Awaitable, Callable

from fastapi import Depends, HTTPException

from api.auth import get_current_user
from lib.config.env import config
from lib.models.file import FileRole
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.file_finalization import finalize_file_from_path
from lib.services.projects import get_project_access
from lib.services.references import add_file_to_reference
from tuspyserver import create_tus_router

logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "unknown"


def _get_pre_create_hook(
    current_user: User = Depends(get_current_user),
) -> Callable[[dict, dict], Awaitable[None]]:
    """Validates user access before upload starts."""

    async def handler(metadata: dict, upload_info: dict) -> None:
        project_id = metadata.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")

        await get_project_access(
            project_id, user=current_user, required_level=AccessLevel.WRITE
        )

    return handler


def _get_completion_hook(
    current_user: User = Depends(get_current_user),
) -> Callable[[str, dict], Awaitable[None]]:
    """Creates file record after upload completes."""

    async def handler(file_path: str, metadata: dict) -> None:
        project_id = metadata.get("project_id", "")

        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")

        role_str = metadata.get("role", FileRole.SUPPORT.value)
        try:
            role = FileRole(role_str)
        except ValueError:
            role = FileRole.SUPPORT

        file_record, was_deduplicated = await finalize_file_from_path(
            file_path=file_path,
            filename=metadata.get("filename", DEFAULT_FILENAME),
            project_id=uuid.UUID(project_id),
            user_id=current_user.id,
            role=role,
        )

        if was_deduplicated:
            try:
                os.remove(file_path)
            except OSError:
                pass

        logger.info(
            "Created file record %s (hash: %s)",
            file_record.id,
            file_record.content_hash,
        )

        reference_id = metadata.get("reference_id")
        if reference_id:
            linked = await add_file_to_reference(
                project_id=project_id,
                file_id=str(file_record.id),
                reference_id=reference_id,
            )
            if not linked:
                logger.error(
                    "Failed to link file %s to reference %s",
                    file_record.id,
                    reference_id,
                )

    return handler


tus_router = create_tus_router(
    prefix="tus",
    files_dir=config.FILE_UPLOADS_MOUNT_PATH,
    max_size=500 * 1024 * 1024,
    days_to_keep=1,
    auth=get_current_user,  # type: ignore[arg-type]
    pre_create_dep=_get_pre_create_hook,  # type: ignore[arg-type]
    upload_complete_dep=_get_completion_hook,  # type: ignore[arg-type]
)
