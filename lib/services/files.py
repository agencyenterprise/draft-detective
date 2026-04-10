import logging
import os
import uuid
from typing import Any, List, Optional, Sequence

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileListItem, FileRole
from lib.models.project import Project
from lib.services.file import FileDocument, create_file_document_from_path
from lib.services.text_sanitization import strip_control_chars
from lib.services.uuid_utils import ensure_uuid

logger = logging.getLogger(__name__)


def _sanitize_for_postgres(value: Any) -> Any:
    """
    Recursively remove control characters from strings in a data structure.

    PostgreSQL's text type (and JSONB) cannot store C0/C1 control characters,
    which may appear in LLM output or document parsing. This function sanitizes
    the data before storage.

    Args:
        value: Any value - strings, dicts, lists, or primitives

    Returns:
        The same structure with control characters removed from all strings
    """
    if isinstance(value, str):
        return strip_control_chars(value)
    elif isinstance(value, dict):
        return {k: _sanitize_for_postgres(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_sanitize_for_postgres(item) for item in value]
    else:
        return value


async def create_file_record(
    project_id: uuid.UUID,
    file_name: str,
    file_path: str,
    file_type: str,
    file_size: int,
    content_hash: str,
    role: FileRole,
    uploaded_by: uuid.UUID,
    original_file_path: Optional[str] = None,
    description: Optional[str] = None,
) -> File:
    """
    Create a file record in the database.

    Args:
        project_id: UUID of the project this file belongs to
        file_name: Original filename from user upload
        file_path: Path to file in FILE_UPLOADS_MOUNT_PATH
        file_type: MIME type of the file
        file_size: Size of file in bytes
        content_hash: xxhash of file content for deduplication
        role: Role of file in workflow (MAIN, SUPPORT, etc.)
        uploaded_by: UUID of user who uploaded the file
        original_file_path: Optional path to original file if converted
        description: Optional description of the file

    Returns:
        Created File model instance
    """
    async with get_async_db_session() as session:
        file = File(
            project_id=project_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            content_hash=content_hash,
            role=role,
            uploaded_by=uploaded_by,
            original_file_path=original_file_path,
            description=description,
        )
        session.add(file)
        await session.commit()
        await session.refresh(file)
        return file


async def get_file_by_id(file_id: uuid.UUID | str) -> File:
    """
    Get a single file by ID.

    Args:
        file_id: UUID of the file to retrieve

    Returns:
        File model instance

    Raises:
        HTTPException: 404 if file not found
    """
    file_id = ensure_uuid(file_id, "file ID")

    async with get_async_db_session() as session:
        stmt = select(File).where(col(File.id) == file_id)
        result = await session.execute(stmt)
        file = result.scalar_one_or_none()

        if file is None:
            raise HTTPException(status_code=404, detail="File not found")

        return file


async def get_files_by_project_id(
    project_id: uuid.UUID | str,
    roles: Optional[List[FileRole]] = None,
) -> List[File]:
    """
    Get all files by project ID, optionally filtered by role.
    """
    project_id = ensure_uuid(project_id, "project ID")
    async with get_async_db_session() as session:
        stmt = select(File).where(col(File.project_id) == project_id)
        if roles is not None:
            stmt = stmt.where(col(File.role).in_(roles))
        result = await session.execute(stmt)
        files = result.scalars().all()
        return list(files)


async def get_project_files_list_items(
    project_id: uuid.UUID | str,
) -> List[FileListItem]:
    """
    Get files for a project as lightweight list items (excludes markdown and summary).

    Note: Excludes SUPPORTING_CANDIDATE files as they are temporary files during
    reference downloading and should not be shown to users.
    """
    project_id = ensure_uuid(project_id, "project ID")
    async with get_async_db_session() as session:
        stmt = select(File).where(
            col(File.project_id) == project_id,
            col(File.role) != FileRole.SUPPORTING_CANDIDATE,
        )
        result = await session.execute(stmt)
        files = result.scalars().all()
        return [FileListItem.model_validate(f, from_attributes=True) for f in files]


async def get_supporting_candidate_files(project_id: uuid.UUID | str) -> List[File]:
    """
    Get all files with SUPPORTING_CANDIDATE role for a project.

    These are files downloaded by the reference fetcher that are pending validation.
    """
    project_id = ensure_uuid(project_id, "project ID")
    async with get_async_db_session() as session:
        stmt = select(File).where(
            col(File.project_id) == project_id,
            col(File.role) == FileRole.SUPPORTING_CANDIDATE,
        )
        result = await session.execute(stmt)
        files = result.scalars().all()
        return list(files)


async def update_files_role(
    file_ids: Sequence[uuid.UUID | str], role: FileRole
) -> None:
    """
    Update the role of multiple files.

    Args:
        file_ids: List of file IDs to update
        role: The new role to set
    """
    if not file_ids:
        return

    async with get_async_db_session() as session:
        normalized_ids = [ensure_uuid(fid, "file ID") for fid in file_ids]
        stmt = update(File).where(col(File.id).in_(normalized_ids)).values(role=role)
        await session.execute(stmt)
        await session.commit()


async def update_file_artifacts(
    file_id: uuid.UUID | str,
    markdown: str | None = None,
    summary: dict | None = None,
) -> None:
    """
    Update file artifacts (markdown, summary) for caching processed content.

    Only updates fields that are explicitly provided (not None).

    Args:
        file_id: UUID of the file to update
        markdown: The converted markdown content (optional)
        summary: Document summary as dict (optional)
    """
    file_id = ensure_uuid(file_id, "file ID")

    async with get_async_db_session() as session:
        stmt = select(File).where(col(File.id) == file_id)
        result = await session.execute(stmt)
        file = result.scalar_one_or_none()
        if file is None:
            logger.warning(f"File {file_id} not found, skipping artifact update")
            return

        if markdown is not None:
            file.markdown = _sanitize_for_postgres(markdown)
        if summary is not None:
            file.summary = _sanitize_for_postgres(summary)

        await session.commit()
        logger.debug(f"Updated artifacts for file {file_id}")


async def load_file_document(
    file: File, use_cached_artifacts: bool = True
) -> FileDocument:
    """
    Convert File model to FileDocument, using cached artifacts from DB if available.

    When use_cached_artifacts is True and the file has cached markdown in the database,
    the FileDocument is created directly from the cached data without re-converting.
    Otherwise, creates a FileDocument without markdown (for workflow to convert).

    Args:
        file: File model instance from database
        use_cached_artifacts: If True, use cached markdown from DB when available

    Returns:
        FileDocument with markdown content (from cache or empty)

    Raises:
        FileNotFoundError: If the file doesn't exist on disk
    """
    from langchain_core.messages.utils import count_tokens_approximately

    # Use cached artifacts if available and requested
    if use_cached_artifacts and file.markdown is not None:
        return FileDocument(
            file_id=str(file.id),
            file_path=file.file_path,
            file_name=file.file_name,
            file_type=file.file_type,
            markdown=file.markdown,
            markdown_token_count=count_tokens_approximately([file.markdown]),
            original_file_path=file.original_file_path,
        )

    # Fall back to creating without markdown (for workflow to convert)
    return await create_file_document_from_path(
        file_path=file.file_path,
        file_id=str(file.id),
        file_type=file.file_type,
        original_file_name=file.file_name,
        original_file_path=file.original_file_path,
        markdown_convert=False,
    )


async def check_file_access(file_id: uuid.UUID | str, user_id: uuid.UUID) -> File:
    """
    Check if a user has access to a file by verifying project ownership.

    Args:
        file_id: UUID of the file to check access for
        user_id: UUID of the user requesting access

    Returns:
        File model instance if access is granted

    Raises:
        HTTPException: 400 for invalid file ID, 404 if file not found, 403 if access denied
    """

    # Normalize ID and fail fast on invalid format to avoid DB errors
    file_id = ensure_uuid(file_id, "file ID")

    async with get_async_db_session() as session:
        stmt = (
            select(File, Project)
            .join(Project, col(File.project_id) == col(Project.id))
            .where(col(File.id) == file_id)
        )
        result = (await session.execute(stmt)).one_or_none()

        if result is None:
            raise HTTPException(status_code=404, detail="File not found")

        file, project = result

        if project.user_id is None or project.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this file")

        return file


async def check_file_access_by_share_token(
    file_id: uuid.UUID | str, share_token: str
) -> File:
    """
    Check if a share token grants access to a file.

    Validates that the share token is active and belongs to a project that contains
    the requested file.

    Args:
        file_id: UUID of the file to check access for
        share_token: Share token for public access

    Returns:
        File model instance if access is granted

    Raises:
        HTTPException: 400 for invalid file ID, 404 if file/share not found, 403 if access denied
    """
    from lib.models.project import Project
    from lib.models.share_link import ShareLink

    file_id = ensure_uuid(file_id, "file ID")

    async with get_async_db_session() as session:
        # Get the file and its project
        stmt = (
            select(File, Project)
            .join(Project, col(File.project_id) == col(Project.id))
            .where(col(File.id) == file_id)
        )
        result = (await session.execute(stmt)).one_or_none()

        if result is None:
            raise HTTPException(status_code=404, detail="File not found")

        file, project = result

        # Check if the share token is valid for this project
        share_link_stmt = select(ShareLink).where(
            col(ShareLink.token) == share_token,
            col(ShareLink.is_active).is_(True),
            col(ShareLink.resource_type) == "project",
            col(ShareLink.resource_id) == project.id,
        )
        share_link = (await session.execute(share_link_stmt)).scalar_one_or_none()

        if share_link is None:
            raise HTTPException(
                status_code=403, detail="Invalid or expired share token"
            )

        return file


async def delete_project_files(
    project_id: uuid.UUID | str,
    target_file_ids: Sequence[str] | None = None,
) -> int:
    """
    Delete all files for a project from the database and remove disk files
    only when they are not referenced by other projects.

    Args:
        project_id: UUID of the project to delete files for
        target_file_ids: Optional list of file IDs to delete. If not provided, all files for the project will be deleted.

    Returns:
        The number of files deleted
    """

    normalized_project_id = ensure_uuid(project_id, "project ID")
    deleted_count = 0

    async with get_async_db_session() as session:
        stmt = select(File).where(col(File.project_id) == normalized_project_id)
        result = await session.execute(stmt)
        project_files = result.scalars().all()

        for file in project_files:
            if target_file_ids is not None and str(file.id) not in target_file_ids:
                continue

            if not await _is_path_shared(
                session, file.file_path, normalized_project_id
            ):
                _delete_file_from_disk(file.file_path)

            if file.original_file_path and not await _is_path_shared(
                session, file.original_file_path, normalized_project_id
            ):
                _delete_file_from_disk(file.original_file_path)

            await session.delete(file)
            deleted_count += 1

        await session.commit()

    return deleted_count


async def _is_path_shared(
    session: AsyncSession, path: str, project_id: uuid.UUID
) -> bool:
    """
    Check whether another project references the same file path.
    """
    stmt = (
        select(func.count())
        .select_from(File)
        .where(
            col(File.project_id) != project_id,
            or_(col(File.file_path) == path, col(File.original_file_path) == path),
        )
    )
    result = await session.execute(stmt)
    count = result.scalar_one()
    return count > 0


def _delete_file_from_disk(
    file_path: str,
) -> None:
    """
    Delete a file from the file system.
    """

    try:
        os.remove(file_path)
        logger.info(f"Deleted file from disk: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting file from disk: {e}")
