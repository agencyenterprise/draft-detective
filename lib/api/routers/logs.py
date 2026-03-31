"""
Admin endpoints for listing and downloading daily log files.
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from lib.api.auth import require_admin
from lib.config.env import config as env_config
from lib.models.user import User

router = APIRouter(prefix="/api/admin/logs", tags=["admin"])


class LogFileInfo(BaseModel):
    filename: str
    size_bytes: int
    modified_at: datetime


def _get_log_dir() -> Path:
    return Path(env_config.FILE_UPLOADS_MOUNT_PATH) / "logs"


def _list_log_files() -> list[Path]:
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return []
    return sorted(
        (f for f in log_dir.iterdir() if f.is_file() and f.name.startswith("app.log")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )


def _resolve_safe_path(filename: str) -> Path:
    """Resolve the log file path and ensure it stays within the log directory."""
    log_dir = _get_log_dir().resolve()
    candidate = (log_dir / filename).resolve()
    if not candidate.is_relative_to(log_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")
    return candidate


@router.get("", response_model=list[LogFileInfo])
async def list_logs(_admin: User = Depends(require_admin)) -> list[LogFileInfo]:
    """Return metadata for all available log files, newest first."""
    files = _list_log_files()
    return [
        LogFileInfo(
            filename=f.name,
            size_bytes=f.stat().st_size,
            modified_at=datetime.fromtimestamp(f.stat().st_mtime),
        )
        for f in files
    ]


@router.get("/download/{filename}")
async def download_log(
    filename: str,
    _admin: User = Depends(require_admin),
) -> FileResponse:
    """Download a specific log file by name."""

    log_path = _resolve_safe_path(filename)
    return FileResponse(path=str(log_path), media_type="text/plain", filename=filename)
