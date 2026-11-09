import asyncio
import io
import logging
import os
import re
import unicodedata
import uuid
import zipfile
from collections.abc import Sequence

from fastapi import HTTPException

from lib.config.env import config
from lib.models.file import File, FileRole
from lib.services.files.service import get_files_by_project_id

logger = logging.getLogger(__name__)

# What "download all" bundles when the caller names no roles: the main
# document and its supporting files. The route's query default reads this too.
DEFAULT_DOWNLOAD_ROLES: tuple[FileRole, ...] = (FileRole.MAIN, FileRole.SUPPORT)

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


# What Windows refuses in a file name (uploads only reject "/"): these
# characters, and the device names, whatever extension follows them.
_WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"{port}{i}" for port in ("COM", "LPT") for i in range(1, 10)}
)


def _portable_name(file_name: str) -> str:
    """The name as every common OS can extract it. Windows also drops trailing
    dots and spaces, so they go here rather than silently on extraction."""
    name = _WINDOWS_FORBIDDEN.sub("_", file_name).rstrip(". ") or "file"
    if name.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        name = f"_{name}"
    return name


def _collision_key(name: str) -> str:
    """Names that extract to the same file: most file systems ignore case, and
    macOS treats canonically equivalent spellings (NFC/NFD) as one."""
    return unicodedata.normalize("NFC", name).casefold()


def _entry_name(file_name: str, taken: set[str]) -> str:
    """The file's own name, made portable, and numbered like ``report (2).pdf``
    only when an earlier entry would extract to the same file."""
    portable = _portable_name(file_name)
    stem, ext = os.path.splitext(portable)
    name, n = portable, 1
    while _collision_key(name) in taken:
        n += 1
        name = f"{stem} ({n}){ext}"
    return name


async def create_project_files_zip(
    project_id: uuid.UUID | str,
    roles: Sequence[FileRole] | None = None,
) -> tuple[io.BytesIO, int]:
    """
    Create a ZIP archive containing all files for a project.

    Args:
        project_id: UUID of the project
        roles: The file roles to include. None means ``DEFAULT_DOWNLOAD_ROLES``.

    Returns:
        Tuple of (BytesIO buffer containing the ZIP file, number of files added)

    Raises:
        HTTPException: 404 if no files found or no accessible files
    """
    if roles is None:
        roles = DEFAULT_DOWNLOAD_ROLES

    files = await get_files_by_project_id(project_id, roles=roles)

    if not files:
        raise HTTPException(status_code=404, detail="No files found for this project")

    zip_buffer, files_added = await asyncio.to_thread(_build_zip_archive, files)

    if files_added == 0:
        raise HTTPException(
            status_code=404, detail="No accessible files found for this project"
        )

    return zip_buffer, files_added


def _build_zip_archive(files: list[File]) -> tuple[io.BytesIO, int]:
    """Build the ZIP archive synchronously (intended to run in a thread)."""
    zip_buffer = io.BytesIO()
    files_added = 0
    taken: set[str] = set()
    # Oldest upload first, so the same files get the same names on every
    # download: the earliest keeps the plain name when two share one.
    ordered = sorted(files, key=lambda f: (f.created_at, str(f.id)))

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for file in ordered:
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
                entry_name = _entry_name(file.file_name, taken)
                zip_file.write(file.file_path, entry_name, compress_type=compression)
                taken.add(_collision_key(entry_name))
                files_added += 1
            except Exception as e:
                logger.error(
                    f"Error adding file {file.id} ({file.file_name}) to zip: {e}"
                )
                continue

    zip_buffer.seek(0)
    return zip_buffer, files_added
