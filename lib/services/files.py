import io
import logging
import os
import uuid
import zipfile
from typing import List, Optional, Sequence, Tuple

from fastapi import HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from lib.config.database import get_db
from lib.config.env import config
from lib.models.file import File, FileRole
from lib.services.file import FileDocument, create_file_document_from_path

logger = logging.getLogger(__name__)


def _normalize_uuid(value: uuid.UUID | str, field_name: str) -> uuid.UUID:
    """
    Ensure a UUID value is actually a uuid.UUID, returning 400 on bad formats.
    """
    if isinstance(value, uuid.UUID):
        return value

    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name} format: {value}"
        )


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
    with get_db() as db:
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
        db.add(file)
        db.commit()
        db.refresh(file)
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
    file_id = _normalize_uuid(file_id, "file ID")

    with get_db() as db:
        file = db.query(File).filter(File.id == file_id).first()

        if file is None:
            raise HTTPException(status_code=404, detail="File not found")

        return file


async def get_files_by_project_id(project_id: uuid.UUID | str) -> List[File]:
    """
    Get all files by project ID.
    """
    project_id = _normalize_uuid(project_id, "project ID")
    with get_db() as db:
        files = db.query(File).filter(File.project_id == project_id).all()
        return files


async def get_files_count_by_project_id(project_id: uuid.UUID | str) -> int:
    """
    Get the number of files by project ID.
    """
    project_id = _normalize_uuid(project_id, "project ID")
    with get_db() as db:
        count = db.query(func.count()).filter(File.project_id == project_id).scalar()
        return count


async def get_supporting_candidate_files(project_id: uuid.UUID | str) -> List[File]:
    """
    Get all files with SUPPORTING_CANDIDATE role for a project.

    These are files downloaded by the reference fetcher that are pending validation.
    """
    project_id = _normalize_uuid(project_id, "project ID")
    with get_db() as db:
        files = (
            db.query(File)
            .filter(File.project_id == project_id)
            .filter(File.role == FileRole.SUPPORTING_CANDIDATE)
            .all()
        )
        return files


def update_files_role(file_ids: Sequence[uuid.UUID | str], role: FileRole) -> None:
    """
    Update the role of multiple files.

    Args:
        file_ids: List of file IDs to update
        role: The new role to set
    """
    if not file_ids:
        return

    with get_db() as db:
        normalized_ids = [_normalize_uuid(fid, "file ID") for fid in file_ids]
        db.query(File).filter(File.id.in_(normalized_ids)).update(
            {File.role: role}, synchronize_session=False
        )
        db.commit()


def update_file_artifacts(
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
    file_id = _normalize_uuid(file_id, "file ID")

    with get_db() as db:
        file = db.query(File).filter(File.id == file_id).first()
        if file is None:
            logger.warning(f"File {file_id} not found, skipping artifact update")
            return

        if markdown is not None:
            file.markdown = markdown
        if summary is not None:
            file.summary = summary

        db.commit()
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
    file_id = _normalize_uuid(file_id, "file ID")

    with get_db() as db:
        from lib.models.project import Project

        result = (
            db.query(File, Project)
            .join(Project, File.project_id == Project.id)
            .filter(File.id == file_id)
            .first()
        )

        if result is None:
            raise HTTPException(status_code=404, detail="File not found")

        file, project = result

        if project.user_id is None or project.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this file")

        return file


def delete_project_files(
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

    normalized_project_id = _normalize_uuid(project_id, "project ID")
    deleted_count = 0

    with get_db() as db:
        project_files = (
            db.query(File).filter(File.project_id == normalized_project_id).all()
        )

        for file in project_files:
            if target_file_ids is not None and str(file.id) not in target_file_ids:
                continue

            if not _is_path_shared(db, file.file_path, normalized_project_id):
                _delete_file_from_disk(file.file_path)

            if file.original_file_path and not _is_path_shared(
                db, file.original_file_path, normalized_project_id
            ):
                _delete_file_from_disk(file.original_file_path)

            db.delete(file)
            deleted_count += 1

        db.commit()

    return deleted_count


def _is_path_shared(db: Session, path: str, project_id: uuid.UUID) -> bool:
    """
    Check whether another project references the same file path.
    """

    found_file = (
        db.query(File)
        .filter(File.project_id != project_id)
        .filter(or_(File.file_path == path, File.original_file_path == path))
        .first()
    )

    return found_file is not None


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


async def create_project_files_zip(
    project_id: uuid.UUID | str,
    roles: Optional[List[FileRole]] = None,
) -> Tuple[io.BytesIO, int]:
    """
    Create a ZIP archive containing all files for a project.

    Args:
        project_id: UUID of the project
        roles: Optional list of file roles to filter by. If None, main and support files are included by default.

    Returns:
        Tuple of (BytesIO buffer containing the ZIP file, number of files added)

    Raises:
        HTTPException: 404 if no files found or no accessible files
    """
    files = await get_files_by_project_id(project_id)

    # Default to main and support files if no roles are specified
    if roles is None:
        roles = [FileRole.MAIN, FileRole.SUPPORT]

    # Filter files by roles if specified
    if roles:
        files = [f for f in files if f.role in roles]

    if not files:
        raise HTTPException(status_code=404, detail="No files found for this project")

    # Create in-memory zip file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        files_added = 0
        for file in files:
            # Security check: ensure file path is within upload mount path
            if not file.file_path.startswith(config.FILE_UPLOADS_MOUNT_PATH):
                logger.warning(
                    f"Skipping file {file.id} - path outside mount path: {file.file_path}"
                )
                continue

            # Check if file exists on disk
            if not os.path.isfile(file.file_path):
                logger.warning(
                    f"Skipping file {file.id} - file not found on disk: {file.file_path}"
                )
                continue

            try:
                # Add file to zip using original filename
                zip_file.write(file.file_path, f"{str(file.id)[:4]}_{file.file_name}")
                files_added += 1
            except Exception as e:
                # Log error but continue with other files
                logger.error(
                    f"Error adding file {file.id} ({file.file_name}) to zip: {e}"
                )
                continue

    if files_added == 0:
        raise HTTPException(
            status_code=404, detail="No accessible files found for this project"
        )

    zip_buffer.seek(0)
    return zip_buffer, files_added
