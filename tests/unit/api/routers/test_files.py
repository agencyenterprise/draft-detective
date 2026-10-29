"""Unit tests for the single-file download endpoint."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import FileResponse

from lib.api.routers.files import download_file
from lib.models.file import File, FileRole


def _file(path: Path, file_name: str) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        file_name=file_name,
        file_path=str(path),
        file_type="application/pdf",
        file_size=path.stat().st_size,
        content_hash="abc123",
        role=FileRole.MAIN,
        uploaded_by=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_download_is_named_after_the_upload(tmp_path: Path):
    """The browser saves the file under its uploaded name, not its id, and a PDF
    still opens in the tab rather than downloading."""
    stored = tmp_path / "stored.pdf"
    stored.write_bytes(b"%PDF-1.4")
    file = _file(stored, "Relatório final.pdf")

    with (
        patch(
            "lib.api.routers.files.config",
            MagicMock(FILE_UPLOADS_MOUNT_PATH=str(tmp_path)),
        ),
        patch(
            "lib.api.routers.files.check_file_access_by_share_token",
            AsyncMock(return_value=file),
        ),
    ):
        response = await download_file(
            str(file.id), share_token="token", current_user=None
        )

    assert isinstance(response, FileResponse)
    assert response.headers["content-disposition"] == (
        "inline; filename*=utf-8''Relat%C3%B3rio%20final.pdf"
    )
