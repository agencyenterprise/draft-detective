import logging
import os
import uuid
from typing import List, Optional

from fastapi import HTTPException

from lib.config.database import get_db
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
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")


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


async def load_file_document(file: File) -> FileDocument:
    """
    Convert File model to FileDocument with markdown loaded.

    This function lazy-loads the markdown content from the file system
    on demand, as markdown is not stored in the database.

    Args:
        file: File model instance from database

    Returns:
        FileDocument with markdown content loaded

    Raises:
        FileNotFoundError: If the file doesn't exist on disk
    """
    return await create_file_document_from_path(
        file_path=file.file_path,
        original_file_name=file.file_name,
        markdown_convert=False,
        original_file_path=file.original_file_path,
        file_id=str(file.id),
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


async def delete_file(file_or_id: File | uuid.UUID | str) -> None:
    """
    Delete a file from the file system and database.

    Args:
        file_or_id: File model instance or UUID of the file to delete

    Returns:
        None
    """

    file: File = (
        file_or_id if isinstance(file_or_id, File) else await get_file_by_id(file_or_id)
    )

    await _delete_file_from_disk(file)
    with get_db() as db:
        db.delete(file)
        db.commit()

    return None


async def _delete_file_from_disk(file: File) -> None:
    """
    Delete a file from the file system.

    Args:
        file: File model instance to delete

    Returns:
        None
    """

    try:
        os.remove(file.file_path)
        logger.info(f"Deleted file from disk: {file.file_path}")
    except Exception as e:
        logger.error(f"Error deleting file from disk: {e}")

    if file.original_file_path:
        try:
            os.remove(file.original_file_path)
            logger.info(f"Deleted original file from disk: {file.original_file_path}")
        except Exception as e:
            logger.error(f"Error deleting original file from disk: {e}")
