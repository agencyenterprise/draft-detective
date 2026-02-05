"""
Upload service for resumable file uploads.

Provides the main interface for creating upload sessions, handling chunks,
and finalizing uploads. Reuses existing file processing logic.
"""

import logging
import os
import uuid
from typing import Optional

import aiofiles
import magic
from pydantic import BaseModel
from xxhash import xxh128

from lib.config.env import config
from lib.models.file import File, FileRole
from lib.services.files import create_file_record
from lib.services.upload.storage import UploadInfo
from lib.services.upload.tus_handler import (
    ChunkUploadResult,
    TusProtocolHandler,
    tus_handler,
)

logger = logging.getLogger(__name__)


class UploadSessionResponse(BaseModel):
    """Response for upload session creation."""

    session_id: str
    upload_url: str
    chunk_size: int


class UploadStatusResponse(BaseModel):
    """Response for upload status query."""

    session_id: str
    filename: str
    total_size: int
    uploaded_size: int
    progress_percent: float
    is_complete: bool


def _validate_filename(filename: str) -> None:
    """Validate filename has no path separators."""
    if not filename or not filename.strip():
        raise ValueError("Uploaded file has no filename")
    if os.sep in filename or (os.altsep and os.altsep in filename):
        raise ValueError("Filename cannot contain path separators")


async def finalize_uploaded_file(
    content: bytes,
    filename: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: FileRole,
) -> File:
    """
    Core upload finalization - reused by both direct and chunked uploads.

    Computes content hash, saves to disk with deduplication, detects MIME type,
    and creates database record.
    """
    _validate_filename(filename)

    content_hash = xxh128(content).hexdigest()
    file_extension = os.path.splitext(filename)[1]
    file_path = os.path.join(
        config.FILE_UPLOADS_MOUNT_PATH, content_hash + file_extension
    )
    file_size = len(content)

    if os.path.exists(file_path):
        logger.info(
            "File %s with hash %s already exists at %s, skipping save",
            filename,
            content_hash,
            file_path,
        )
    else:
        logger.info(
            "Saving file %s with hash %s to %s", filename, content_hash, file_path
        )
        if file_size == 0:
            logger.warning("Uploaded file %s is empty!", filename)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        if not os.path.exists(file_path):
            raise OSError(f"File was not created at {file_path}")

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
    )


class UploadService:
    """Service for managing resumable file uploads."""

    def __init__(self, handler: Optional[TusProtocolHandler] = None):
        self.handler = handler or tus_handler

    async def _get_upload_info_or_raise(self, session_id: str) -> UploadInfo:
        """Get upload info or raise FileNotFoundError."""
        info = await self.handler.get_upload_info(session_id)
        if not info:
            raise FileNotFoundError(f"Upload session {session_id} not found")
        return info

    async def verify_session_owner(self, session_id: str, user_id: uuid.UUID) -> None:
        """Verify that the user owns the upload session. Raises PermissionError if not."""
        info = await self._get_upload_info_or_raise(session_id)
        if info.user_id != str(user_id):
            raise PermissionError("You do not have permission to access this upload")

    async def create_session(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        filename: str,
        file_size: int,
        base_url: str,
    ) -> UploadSessionResponse:
        """Create a new upload session."""
        result = await self.handler.create_upload(
            filename=filename,
            file_size=file_size,
            project_id=str(project_id),
            user_id=str(user_id),
        )

        return UploadSessionResponse(
            session_id=result.session_id,
            upload_url=f"{base_url}/api/upload/{result.session_id}",
            chunk_size=self.handler.config.chunk_size,
        )

    async def upload_chunk(
        self,
        session_id: str,
        data: bytes,
        offset: int,
    ) -> ChunkUploadResult:
        """Upload a chunk of data."""
        return await self.handler.upload_chunk(session_id, data, offset)

    async def get_upload_offset(self, session_id: str) -> int:
        """Get current upload offset for resuming."""
        return await self.handler.get_upload_offset(session_id)

    async def get_status(self, session_id: str) -> UploadStatusResponse:
        """Get upload session status."""
        info = await self._get_upload_info_or_raise(session_id)
        progress = (
            (info.uploaded_size / info.total_size * 100) if info.total_size > 0 else 0
        )

        return UploadStatusResponse(
            session_id=session_id,
            filename=info.filename,
            total_size=info.total_size,
            uploaded_size=info.uploaded_size,
            progress_percent=round(progress, 2),
            is_complete=info.uploaded_size >= info.total_size,
        )

    async def complete_upload(
        self,
        session_id: str,
        role: FileRole = FileRole.SUPPORT,
    ) -> File:
        """Complete an upload and create the file record."""
        info = await self._get_upload_info_or_raise(session_id)

        if info.uploaded_size < info.total_size:
            raise ValueError(
                f"Upload incomplete: {info.uploaded_size}/{info.total_size} bytes"
            )

        file_path = await self.handler.get_completed_file_path(session_id)
        if not file_path:
            raise ValueError("Upload not complete")

        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        file_record = await finalize_uploaded_file(
            content=content,
            filename=info.filename,
            project_id=uuid.UUID(info.project_id),
            user_id=uuid.UUID(info.user_id),
            role=role,
        )

        await self.handler.cancel_upload(session_id)
        logger.info(
            "Completed upload session %s, created file %s", session_id, file_record.id
        )

        return file_record

    async def cancel_upload(self, session_id: str) -> None:
        """Cancel and cleanup an upload session."""
        await self.handler.cancel_upload(session_id)


# Default service instance
upload_service = UploadService()
