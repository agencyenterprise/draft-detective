"""Unit tests for the single-file download endpoint."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import FileResponse

from lib.api.routers.files import download_file
from lib.models.file import File, FileRole


def _file(path: Path, file_name: str, file_type: str = "application/pdf") -> File:
    return File(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        file_name=file_name,
        file_path=str(path),
        file_type=file_type,
        file_size=path.stat().st_size,
        content_hash="abc123",
        role=FileRole.MAIN,
        uploaded_by=uuid.uuid4(),
    )


async def _download(tmp_path: Path, file: File) -> FileResponse:
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
    return response


@pytest.mark.asyncio
async def test_download_is_named_after_the_upload(tmp_path: Path):
    """The browser saves the file under its uploaded name, not its id, and a PDF
    still opens in the tab rather than downloading."""
    stored = tmp_path / "stored.pdf"
    stored.write_bytes(b"%PDF-1.4")
    file = _file(stored, "Relatório final.pdf")

    response = await _download(tmp_path, file)

    assert response.headers["content-disposition"] == (
        "inline; filename*=utf-8''Relat%C3%B3rio%20final.pdf"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file_type",
    ["text/html", "image/svg+xml", "application/xhtml+xml", "text/xml"],
)
async def test_active_content_downloads_instead_of_rendering(
    tmp_path: Path, file_type: str
):
    """A file the browser would run script from never renders inline.

    Its type comes from its bytes (libmagic on upload, the document for an
    extracted image, the remote server for a downloaded reference), so a
    markdown upload that opens with ``<script>`` is stored as text/html. Shown
    inline through the app's same-origin download route, its script would run
    with the viewer's session.
    """
    stored = tmp_path / "stored.md"
    stored.write_bytes(b"<script>fetch('/api/auth/session')</script>")
    file = _file(stored, "notes.md", file_type)

    response = await _download(tmp_path, file)

    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
@pytest.mark.parametrize("file_type", ["image/png", "image/jpeg", "text/plain"])
async def test_passive_content_still_opens_in_the_tab(tmp_path: Path, file_type: str):
    stored = tmp_path / "stored.bin"
    stored.write_bytes(b"x")
    file = _file(stored, "figure", file_type)

    response = await _download(tmp_path, file)

    assert response.headers["content-disposition"].startswith("inline;")
