"""
Tus protocol handler for resumable uploads.

Abstracts the Tus protocol details from the rest of the application.
"""

import logging
import uuid
from typing import Optional

from pydantic import BaseModel

from lib.config.env import config as env_config
from lib.services.upload.storage import LocalUploadStorage, UploadInfo, local_storage

logger = logging.getLogger(__name__)

DEFAULT_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


class TusUploadConfig(BaseModel):
    """Configuration for Tus upload handler."""

    chunk_size: int = env_config.UPLOAD_CHUNK_SIZE
    session_ttl: int = env_config.UPLOAD_SESSION_TTL_HOURS * 60 * 60
    max_file_size: int = DEFAULT_MAX_FILE_SIZE


class CreateUploadResult(BaseModel):
    """Result of creating an upload session."""

    session_id: str
    upload_offset: int


class ChunkUploadResult(BaseModel):
    """Result of uploading a chunk."""

    upload_offset: int
    is_complete: bool


class TusProtocolHandler:
    """Handler for Tus protocol operations."""

    def __init__(
        self,
        storage: Optional[LocalUploadStorage] = None,
        config: Optional[TusUploadConfig] = None,
    ):
        self.storage = storage or local_storage
        self.config = config or TusUploadConfig()

    async def _get_info_or_raise(self, session_id: str) -> UploadInfo:
        """Get upload info or raise FileNotFoundError."""
        info = await self.storage.get_upload_info(session_id)
        if not info:
            raise FileNotFoundError(f"Upload session {session_id} not found")
        return info

    async def create_upload(
        self,
        filename: str,
        file_size: int,
        project_id: str,
        user_id: str,
    ) -> CreateUploadResult:
        """Create a new upload session (Tus POST)."""
        if file_size > self.config.max_file_size:
            raise ValueError(
                f"File size {file_size} exceeds maximum {self.config.max_file_size}"
            )

        session_id = str(uuid.uuid4())

        await self.storage.create_session(
            session_id=session_id,
            filename=filename,
            total_size=file_size,
            project_id=project_id,
            user_id=user_id,
        )

        logger.info(
            "Created Tus upload session %s for %s (%d bytes)",
            session_id,
            filename,
            file_size,
        )

        return CreateUploadResult(session_id=session_id, upload_offset=0)

    async def upload_chunk(
        self,
        session_id: str,
        data: bytes,
        offset: int,
    ) -> ChunkUploadResult:
        """Upload a chunk of data (Tus PATCH)."""
        info = await self._get_info_or_raise(session_id)

        new_offset = await self.storage.append_chunk(session_id, data, offset)
        is_complete = new_offset >= info.total_size

        if is_complete:
            logger.info("Upload session %s completed", session_id)

        return ChunkUploadResult(upload_offset=new_offset, is_complete=is_complete)

    async def get_upload_offset(self, session_id: str) -> int:
        """Get current upload offset (Tus HEAD)."""
        info = await self._get_info_or_raise(session_id)
        return info.uploaded_size

    async def get_upload_info(self, session_id: str) -> Optional[UploadInfo]:
        """Get full upload session information."""
        return await self.storage.get_upload_info(session_id)

    async def cancel_upload(self, session_id: str) -> None:
        """Cancel and clean up an upload session (Tus DELETE)."""
        await self.storage.cleanup(session_id)
        logger.info("Cancelled upload session %s", session_id)

    async def get_completed_file_path(self, session_id: str) -> Optional[str]:
        """Get path to completed file, or None if incomplete."""
        return await self.storage.get_completed_file_path(session_id)


# Default handler instance
tus_handler = TusProtocolHandler()
