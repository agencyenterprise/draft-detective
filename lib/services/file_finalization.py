"""
Shared file finalization logic for uploads.

Handles content hashing, deduplication, MIME detection, and database record creation.
Used by both direct multipart uploads and TUS resumable uploads.
"""

import logging
import os
import uuid

import aiofiles
import magic
from xxhash import xxh128

from lib.config.env import config
from lib.models.file import File, FileRole
from lib.services.files import create_file_record

logger = logging.getLogger(__name__)


def validate_filename(filename: str) -> None:
    """Validate filename has no path separators."""
    if not filename or not filename.strip():
        raise ValueError("Uploaded file has no filename")
    if os.sep in filename or (os.altsep and os.altsep in filename):
        raise ValueError("Filename cannot contain path separators")


async def finalize_file(
    content: bytes,
    filename: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: FileRole,
    revision: int | None = None,
) -> File:
    """
    Finalize an uploaded file: hash, deduplicate, save, detect MIME, create record.
    """
    validate_filename(filename)

    content_hash = xxh128(content).hexdigest()
    file_extension = os.path.splitext(filename)[1]
    file_path = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, content_hash + file_extension)
    file_size = len(content)

    if os.path.exists(file_path):
        logger.info("File %s already exists (hash: %s), reusing", filename, content_hash)
    else:
        if file_size == 0:
            logger.warning("Uploaded file %s is empty", filename)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

    file_type = magic.from_buffer(content, mime=True)

    return await create_file_record(
        project_id=project_id,
        file_name=filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        content_hash=content_hash,
        role=role,
        uploaded_by=user_id,
        revision=revision,
    )


async def finalize_file_from_path(
    file_path: str,
    filename: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: FileRole,
    revision: int | None = None,
) -> tuple[File, bool]:
    """
    Finalize a file that's already on disk (e.g., from TUS upload).
    
    Returns (file_record, was_deduplicated) - caller should clean up source if deduplicated.
    """
    validate_filename(filename)

    async with aiofiles.open(file_path, "rb") as f:
        content = await f.read()

    content_hash = xxh128(content).hexdigest()
    file_extension = os.path.splitext(filename)[1]
    permanent_path = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, content_hash + file_extension)

    was_deduplicated = os.path.exists(permanent_path)
    if not was_deduplicated:
        import shutil
        shutil.move(file_path, permanent_path)
        logger.info("Moved %s to permanent location (hash: %s)", filename, content_hash)

    file_type = magic.from_buffer(content, mime=True)

    file_record = await create_file_record(
        project_id=project_id,
        file_name=filename,
        file_path=permanent_path,
        file_type=file_type,
        file_size=len(content),
        content_hash=content_hash,
        role=role,
        uploaded_by=user_id,
        revision=revision,
    )

    return file_record, was_deduplicated

