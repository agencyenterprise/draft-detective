"""TUS resumable upload router using tuspyserver."""

import logging
import os
import uuid
from typing import Awaitable, Callable

from fastapi import Depends, HTTPException

from lib.api.auth import get_current_user
from lib.config.env import config
from lib.models.file import FileRole
from lib.models.project import AccessLevel, Project
from lib.models.user import User
from lib.services.file_finalization import finalize_file_from_path
from lib.services.files import get_files_by_project_id
from lib.services.projects import get_project_access
from lib.services.references import add_file_to_reference
from lib.workflows.reference_file_matching.state import MatchSource
from tuspyserver import create_tus_router

logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "unknown"


def _parse_role(metadata: dict) -> FileRole:
    """Read the file role from upload metadata, defaulting to SUPPORT."""
    try:
        return FileRole(metadata.get("role", FileRole.SUPPORT.value))
    except ValueError:
        return FileRole.SUPPORT


def _resolve_file_revision(metadata: dict, role: FileRole, project: Project) -> int | None:
    """Resolve the revision an uploaded file belongs to.

    Supporting documents are shared across revisions (``None``). A main document
    always defines the current revision. Reviewer memos review a *specific*
    draft, which is not always the current one — an author may replace the main
    document before uploading the memos that reviewed the previous draft — so
    clients may target that draft with a ``revision`` metadata field. Omitting it
    keeps the historical behaviour of attaching to the current revision.
    Response memos describe the current draft, so like a main document they
    always attach to the current revision.
    """
    raw = metadata.get("revision")
    has_explicit_revision = raw is not None and str(raw).strip() != ""

    # Only MAIN and the memo roles are revision-scoped. Everything else is
    # shared across revisions — including SUPPORTING_CANDIDATE, the temporary
    # role the reference downloader uses before promoting a file to SUPPORT.
    if role not in (FileRole.MAIN, FileRole.REVIEWER_MEMO, FileRole.RESPONSE_MEMO):
        return None

    if role in (FileRole.MAIN, FileRole.RESPONSE_MEMO):
        # A main document defines its revision; back-dating one would collide
        # with the one-main-per-revision guard below and corrupt the timeline.
        # A response memo back-dated onto an older draft would be read against
        # a draft it does not describe.
        if has_explicit_revision and str(raw).strip() != str(project.current_revision):
            raise HTTPException(
                status_code=400,
                detail=(
                    "revision cannot be set for main documents"
                    if role == FileRole.MAIN
                    else "revision cannot be set for response memos"
                ),
            )
        return project.current_revision

    if not has_explicit_revision:
        return project.current_revision

    try:
        revision = int(str(raw).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="revision must be an integer")

    if not 1 <= revision <= project.current_revision:
        raise HTTPException(
            status_code=400,
            detail=f"revision must be between 1 and {project.current_revision}",
        )
    return revision


def _get_pre_create_hook(
    current_user: User = Depends(get_current_user),
) -> Callable[[dict, dict], Awaitable[None]]:
    """Validates user access and metadata before upload starts."""

    async def handler(metadata: dict, upload_info: dict) -> None:
        project_id = metadata.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")

        project, _ = await get_project_access(
            project_id, user=current_user, required_level=AccessLevel.WRITE
        )

        # Validate the target revision here as well as on completion, so a bad
        # value fails before the client uploads the whole file.
        _resolve_file_revision(metadata, _parse_role(metadata), project)

    return handler


def _get_completion_hook(
    current_user: User = Depends(get_current_user),
) -> Callable[[str, dict], Awaitable[None]]:
    """Creates file record after upload completes."""

    async def handler(file_path: str, metadata: dict) -> None:
        project_id = metadata.get("project_id", "")

        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")

        role = _parse_role(metadata)

        project, _ = await get_project_access(
            project_id, user=current_user, required_level=AccessLevel.WRITE
        )

        revision = _resolve_file_revision(metadata, role, project)

        if role == FileRole.MAIN:
            # Validate: only one MAIN file per revision
            existing_main = await get_files_by_project_id(
                uuid.UUID(project_id), roles=[FileRole.MAIN], revision=revision
            )
            if existing_main:
                raise HTTPException(
                    status_code=409,
                    detail="Project already has a main document for the current revision. Create a new revision first.",
                )

        file_record, was_deduplicated = await finalize_file_from_path(
            file_path=file_path,
            filename=metadata.get("filename", DEFAULT_FILENAME),
            project_id=uuid.UUID(project_id),
            user_id=current_user.id,
            role=role,
            revision=revision,
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
                source=MatchSource.MANUAL_UPLOAD,
                revision=project.current_revision,
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
