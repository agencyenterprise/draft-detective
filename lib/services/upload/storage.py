"""
Storage abstraction for resumable file uploads.

Provides a protocol for storage backends and a local filesystem implementation
that stores upload chunks in the configured FILE_UPLOADS_MOUNT_PATH.
"""

import logging
import os
import shutil
from typing import Optional, Protocol

import aiofiles
from pydantic import BaseModel

from lib.config.env import config

logger = logging.getLogger(__name__)

# Metadata file format: filename, total_size, project_id, user_id (one per line)
METADATA_LINE_COUNT = 4


class UploadInfo(BaseModel):
    """Information about an upload session stored on disk."""

    session_id: str
    filename: str
    total_size: int
    uploaded_size: int
    project_id: str
    user_id: str


class UploadStorageProtocol(Protocol):
    """Protocol for upload storage backends."""

    async def create_session(
        self,
        session_id: str,
        filename: str,
        total_size: int,
        project_id: str,
        user_id: str,
    ) -> str:
        """Create a new upload session and return the temp file path."""
        ...

    async def append_chunk(self, session_id: str, data: bytes, offset: int) -> int:
        """Append chunk data at the given offset. Returns new offset."""
        ...

    async def get_upload_info(self, session_id: str) -> Optional[UploadInfo]:
        """Get upload session info. Returns None if not found."""
        ...

    async def get_completed_file_path(self, session_id: str) -> Optional[str]:
        """Get path to completed file. Returns None if upload not complete."""
        ...

    async def cleanup(self, session_id: str) -> None:
        """Clean up temporary files for a session."""
        ...


class LocalUploadStorage:
    """Local filesystem storage for resumable uploads."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or config.FILE_UPLOADS_MOUNT_PATH
        self.temp_dir = os.path.join(self.base_path, "temp")

    def _get_session_dir(self, session_id: str) -> str:
        return os.path.join(self.temp_dir, session_id)

    def _get_data_path(self, session_id: str) -> str:
        return os.path.join(self._get_session_dir(session_id), "data")

    def _get_meta_path(self, session_id: str) -> str:
        return os.path.join(self._get_session_dir(session_id), "meta")

    def _cleanup_session_dir(self, session_id: str) -> None:
        """Remove session directory if it exists."""
        session_dir = self._get_session_dir(session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            logger.info("Cleaned up upload session %s", session_id)

    async def create_session(
        self,
        session_id: str,
        filename: str,
        total_size: int,
        project_id: str,
        user_id: str,
    ) -> str:
        """Create a new upload session directory and metadata file."""
        session_dir = self._get_session_dir(session_id)

        # Clean up any existing session with this ID (shouldn't happen, but be safe)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            logger.warning("Cleaned up existing session directory: %s", session_id)

        os.makedirs(session_dir, exist_ok=True)

        # Write metadata
        meta_content = f"{filename}\n{total_size}\n{project_id}\n{user_id}\n"
        async with aiofiles.open(self._get_meta_path(session_id), "w") as f:
            await f.write(meta_content)

        # Create empty data file
        data_path = self._get_data_path(session_id)
        async with aiofiles.open(data_path, "wb") as f:
            pass

        logger.info(
            "Created upload session %s for file %s (size: %d)",
            session_id,
            filename,
            total_size,
        )
        return data_path

    async def append_chunk(self, session_id: str, data: bytes, offset: int) -> int:
        """Append chunk data at the given offset."""
        data_path = self._get_data_path(session_id)

        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Upload session {session_id} not found")

        current_size = os.path.getsize(data_path)
        if offset != current_size:
            logger.error(
                "Session %s: Offset mismatch - server has %d bytes, client sent offset %d",
                session_id,
                current_size,
                offset,
            )
            raise ValueError(
                f"Offset mismatch: server has {current_size} bytes, client sent offset {offset}"
            )

        async with aiofiles.open(data_path, "ab") as f:
            await f.write(data)

        new_size = current_size + len(data)
        logger.debug(
            "Session %s: appended %d bytes, total %d", session_id, len(data), new_size
        )
        return new_size

    async def get_upload_info(self, session_id: str) -> Optional[UploadInfo]:
        """Get upload session info from metadata file."""
        meta_path = self._get_meta_path(session_id)
        data_path = self._get_data_path(session_id)

        if not os.path.exists(meta_path):
            return None

        async with aiofiles.open(meta_path, "r") as f:
            lines = (await f.read()).strip().split("\n")

        if len(lines) < METADATA_LINE_COUNT:
            return None

        uploaded_size = os.path.getsize(data_path) if os.path.exists(data_path) else 0

        return UploadInfo(
            session_id=session_id,
            filename=lines[0],
            total_size=int(lines[1]),
            uploaded_size=uploaded_size,
            project_id=lines[2],
            user_id=lines[3],
        )

    async def get_completed_file_path(self, session_id: str) -> Optional[str]:
        """Get path to completed file if upload is complete."""
        info = await self.get_upload_info(session_id)
        if info and info.uploaded_size >= info.total_size:
            return self._get_data_path(session_id)
        return None

    async def cleanup(self, session_id: str) -> None:
        """Remove all files for a session."""
        self._cleanup_session_dir(session_id)


# Default storage instance
local_storage = LocalUploadStorage()
