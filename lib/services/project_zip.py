import asyncio
import io
import logging
import os
import uuid
import zipfile
from typing import List, Optional, Tuple

from fastapi import HTTPException

from lib.config.env import config
from lib.models.file import File, FileRole
from lib.services.files import get_files_by_project_id

logger = logging.getLogger(__name__)

# List of file extensions that are already compressed, so we don't need to compress them again.
_COMPRESSED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".zip",
        ".gz",
        ".bz2",
        ".xz",
        ".zst",
        ".mp3",
        ".mp4",
        ".m4a",
        ".aac",
        ".ogg",
        ".webm",
        ".docx",
        ".xlsx",
        ".pptx",
    }
)


def _compression_for(file_name: str) -> int:
    """Return ZIP_STORED for already-compressed formats, ZIP_DEFLATED otherwise."""
    ext = os.path.splitext(file_name)[1].lower()
    if ext in _COMPRESSED_EXTENSIONS:
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


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
    if roles is None:
        roles = [FileRole.MAIN, FileRole.SUPPORT]

    files = await get_files_by_project_id(project_id, roles=roles)

    if not files:
        raise HTTPException(status_code=404, detail="No files found for this project")

    zip_buffer, files_added = await asyncio.to_thread(_build_zip_archive, files)

    if files_added == 0:
        raise HTTPException(
            status_code=404, detail="No accessible files found for this project"
        )

    return zip_buffer, files_added


def _build_zip_archive(files: List[File]) -> Tuple[io.BytesIO, int]:
    """Build the ZIP archive synchronously (intended to run in a thread)."""
    zip_buffer = io.BytesIO()
    files_added = 0

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for file in files:
            if not file.file_path.startswith(config.FILE_UPLOADS_MOUNT_PATH):
                logger.warning(
                    f"Skipping file {file.id} - path outside mount path: {file.file_path}"
                )
                continue

            if not os.path.isfile(file.file_path):
                logger.warning(
                    f"Skipping file {file.id} - file not found on disk: {file.file_path}"
                )
                continue

            try:
                compression = _compression_for(file.file_name)
                zip_file.write(
                    file.file_path,
                    f"{str(file.id)[:4]}_{file.file_name}",
                    compress_type=compression,
                )
                files_added += 1
            except Exception as e:
                logger.error(
                    f"Error adding file {file.id} ({file.file_name}) to zip: {e}"
                )
                continue

    zip_buffer.seek(0)
    return zip_buffer, files_added
