"""
Resumable upload endpoints using Tus protocol.

Provides endpoints for creating upload sessions, uploading chunks,
checking upload status, and completing/canceling uploads.
"""

import base64
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from api.auth import get_current_user
from lib.models.file import File, FileRole
from lib.models.user import User
from lib.services.projects import get_user_project
from lib.services.upload.service import (
    UploadSessionResponse,
    UploadStatusResponse,
    upload_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Tus protocol constants
TUS_VERSION = "1.0.0"
TUS_RESUMABLE = "1.0.0"
TUS_MAX_SIZE = 500 * 1024 * 1024  # 500MB

# Reusable exception
SESSION_NOT_FOUND = HTTPException(status_code=404, detail="Upload session not found")


def _add_tus_headers(response: Response) -> None:
    """Add standard Tus headers to response."""
    response.headers["Tus-Resumable"] = TUS_RESUMABLE
    response.headers["Tus-Version"] = TUS_VERSION


def _parse_tus_metadata(metadata: Optional[str]) -> str:
    """Parse Tus metadata header to extract filename. Returns 'unknown' if not found."""
    if not metadata:
        return "unknown"

    # Tus metadata format: key base64value,key2 base64value2
    for item in metadata.split(","):
        parts = item.strip().split(" ")
        if len(parts) == 2 and parts[0] == "filename":
            try:
                return base64.b64decode(parts[1]).decode("utf-8")
            except Exception:
                pass
    return "unknown"


@router.options("")
@router.options("/{session_id}")
async def tus_options(response: Response):
    """Tus OPTIONS - Return server capabilities."""
    _add_tus_headers(response)
    response.headers["Tus-Extension"] = "creation,termination"
    response.headers["Tus-Max-Size"] = str(TUS_MAX_SIZE)
    return Response(status_code=204, headers=dict(response.headers))


@router.post(
    "", response_model=UploadSessionResponse, status_code=status.HTTP_201_CREATED
)
async def create_upload_session(
    request: Request,
    project_id: str,
    upload_length: int = Header(..., alias="Upload-Length"),
    upload_metadata: Optional[str] = Header(None, alias="Upload-Metadata"),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new upload session (Tus POST).

    Headers:
        Upload-Length: Total file size in bytes
        Upload-Metadata: Base64-encoded metadata (filename required)

    Query params:
        project_id: Project to upload file to

    Returns:
        UploadSessionResponse with session_id and upload_url
    """
    await get_user_project(project_id, user=current_user)

    filename = _parse_tus_metadata(upload_metadata)
    base_url = str(request.base_url).rstrip("/")

    try:
        result = await upload_service.create_session(
            project_id=uuid.UUID(project_id),
            user_id=current_user.id,
            filename=filename,
            file_size=upload_length,
            base_url=base_url,
        )
        return JSONResponse(
            content=result.model_dump(),
            status_code=201,
            headers={
                "Location": result.upload_url,
                "Tus-Resumable": TUS_RESUMABLE,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.head("/{session_id}")
async def get_upload_offset(
    session_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """
    Get current upload offset (Tus HEAD).

    Used by clients to resume interrupted uploads.

    Returns:
        204 with Upload-Offset header
    """
    try:
        await upload_service.verify_session_owner(session_id, current_user.id)
        info = await upload_service.get_status(session_id)
    except FileNotFoundError:
        raise SESSION_NOT_FOUND
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    _add_tus_headers(response)
    response.headers["Upload-Offset"] = str(info.uploaded_size)
    response.headers["Upload-Length"] = str(info.total_size)
    response.headers["Cache-Control"] = "no-store"

    return Response(status_code=204, headers=dict(response.headers))


@router.patch("/{session_id}")
async def upload_chunk(
    session_id: str,
    request: Request,
    response: Response,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    content_type: str = Header(..., alias="Content-Type"),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a chunk of data (Tus PATCH).

    Headers:
        Upload-Offset: Byte offset for this chunk
        Content-Type: Must be application/offset+octet-stream

    Body:
        Raw chunk bytes

    Returns:
        204 with new Upload-Offset header
    """
    if content_type != "application/offset+octet-stream":
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/offset+octet-stream",
        )

    try:
        await upload_service.verify_session_owner(session_id, current_user.id)
        chunk_data = await request.body()
        result = await upload_service.upload_chunk(
            session_id=session_id,
            data=chunk_data,
            offset=upload_offset,
        )
    except FileNotFoundError:
        raise SESSION_NOT_FOUND
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _add_tus_headers(response)
    response.headers["Upload-Offset"] = str(result.upload_offset)
    return Response(status_code=204, headers=dict(response.headers))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_upload(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel and cleanup an upload session (Tus DELETE)."""
    try:
        await upload_service.verify_session_owner(session_id, current_user.id)
        await upload_service.cancel_upload(session_id)
    except FileNotFoundError:
        raise SESSION_NOT_FOUND
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return Response(status_code=204)


@router.get("/{session_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get detailed upload session status. Returns progress information for the upload."""
    try:
        await upload_service.verify_session_owner(session_id, current_user.id)
        return await upload_service.get_status(session_id)
    except FileNotFoundError:
        raise SESSION_NOT_FOUND
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{session_id}/complete", response_model=File)
async def complete_upload(
    session_id: str,
    role: FileRole = FileRole.SUPPORT,
    current_user: User = Depends(get_current_user),
):
    """
    Complete an upload and create the file record.

    Finalizes the upload by computing hash, moving to permanent storage,
    and creating the database record.

    Args:
        session_id: Upload session ID
        role: File role (default: SUPPORT)

    Returns:
        Created File record
    """
    try:
        await upload_service.verify_session_owner(session_id, current_user.id)
        return await upload_service.complete_upload(session_id=session_id, role=role)
    except FileNotFoundError:
        raise SESSION_NOT_FOUND
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
