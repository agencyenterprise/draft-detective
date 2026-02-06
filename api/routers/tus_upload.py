"""TUS resumable upload router using tuspyserver."""

import logging
import os
import uuid
from typing import Awaitable, Callable

from fastapi import Depends, HTTPException

from api.auth import get_current_user
from lib.config.env import config
from lib.models.file import FileRole
from lib.models.user import User
from lib.services.file_finalization import finalize_file_from_path
from lib.services.projects import get_user_project
from tuspyserver import create_tus_router

logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "unknown"

# Stores upload context between pre-create and completion hooks, keyed by user:project:filename
_upload_context: dict[str, dict] = {}


def _context_key(user_id: uuid.UUID, project_id: str, filename: str) -> str:
    return f"{user_id}:{project_id}:{filename or DEFAULT_FILENAME}"


def _get_pre_create_hook(
    current_user: User = Depends(get_current_user),
) -> Callable[[dict, dict], Awaitable[None]]:
    """Validates user access and stores context for completion hook."""

    async def handler(metadata: dict, upload_info: dict) -> None:
        project_id = metadata.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")

        await get_user_project(project_id, user=current_user)

        key = _context_key(
            current_user.id, project_id, metadata.get("filename", DEFAULT_FILENAME)
        )
        _upload_context[key] = {
            "project_id": project_id,
            "user_id": str(current_user.id),
            "role": metadata.get("role", FileRole.SUPPORT.value),
        }

    return handler


def _get_completion_hook(
    current_user: User = Depends(get_current_user),
) -> Callable[[str, dict], Awaitable[None]]:
    """Creates file record after upload completes."""

    async def handler(file_path: str, metadata: dict) -> None:
        project_id = metadata.get("project_id", "")
        key = _context_key(
            current_user.id, project_id, metadata.get("filename", DEFAULT_FILENAME)
        )
        context = _upload_context.pop(key, None)

        if not context:
            context = {
                "project_id": project_id,
                "user_id": str(current_user.id),
                "role": metadata.get("role", FileRole.SUPPORT.value),
            }

        if not context["project_id"]:
            raise HTTPException(status_code=400, detail="project_id is required")

        role_str = context.get("role", FileRole.SUPPORT.value)
        try:
            role = FileRole(role_str)
        except ValueError:
            role = FileRole.SUPPORT

        file_record, was_deduplicated = await finalize_file_from_path(
            file_path=file_path,
            filename=metadata.get("filename", DEFAULT_FILENAME),
            project_id=uuid.UUID(context["project_id"]),
            user_id=uuid.UUID(context["user_id"]),
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
