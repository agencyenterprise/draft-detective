"""Unit tests for project ZIP archive creation."""

import io
import os
import tempfile
import uuid
import zipfile
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.file import File, FileRole
from lib.services.project_zip import (
    _build_zip_archive,
    _compression_for,
    create_project_files_zip,
)

MOUNT_PATH = "/tmp/test-uploads"
CONFIG_PATH = "lib.services.project_zip.config"
GET_FILES_PATH = "lib.services.project_zip.get_files_by_project_id"


def make_file(
    file_name: str = "report.pdf",
    file_path: str | None = None,
    role: FileRole = FileRole.MAIN,
    file_id: uuid.UUID | None = None,
) -> File:
    fid = file_id or uuid.uuid4()
    return File(
        id=fid,
        project_id=uuid.uuid4(),
        file_name=file_name,
        file_path=file_path or f"{MOUNT_PATH}/{fid}/{file_name}",
        file_type="application/pdf",
        file_size=1024,
        content_hash="abc123",
        role=role,
        uploaded_by=uuid.uuid4(),
    )


# --- _compression_for ---


class TestCompressionFor:
    @pytest.mark.parametrize(
        "filename",
        [
            "doc.pdf",
            "image.jpg",
            "image.JPEG",
            "photo.png",
            "anim.gif",
            "pic.webp",
            "archive.zip",
            "archive.gz",
            "archive.bz2",
            "archive.xz",
            "archive.zst",
            "song.mp3",
            "video.mp4",
            "audio.m4a",
            "audio.aac",
            "audio.ogg",
            "video.webm",
            "doc.docx",
            "sheet.xlsx",
            "slides.pptx",
        ],
    )
    def test_compressed_extensions_use_stored(self, filename: str):
        assert _compression_for(filename) == zipfile.ZIP_STORED

    @pytest.mark.parametrize(
        "filename",
        ["notes.txt", "data.csv", "page.html", "code.py", "config.json", "README"],
    )
    def test_uncompressed_extensions_use_deflated(self, filename: str):
        assert _compression_for(filename) == zipfile.ZIP_DEFLATED

    def test_case_insensitive(self):
        assert _compression_for("IMAGE.PNG") == zipfile.ZIP_STORED
        assert _compression_for("Photo.Jpg") == zipfile.ZIP_STORED


# --- _build_zip_archive ---


class TestBuildZipArchive:
    def _create_temp_file(self, tmpdir: str, file_obj: File) -> str:
        os.makedirs(os.path.dirname(file_obj.file_path), exist_ok=True)
        with open(file_obj.file_path, "w") as f:
            f.write(f"content of {file_obj.file_name}")
        return file_obj.file_path

    @patch(CONFIG_PATH)
    def test_adds_files_to_zip(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH

        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = make_file(file_name="report.pdf", file_path=f"{MOUNT_PATH}/a/report.pdf")
            f2 = make_file(file_name="notes.txt", file_path=f"{MOUNT_PATH}/b/notes.txt")
            self._create_temp_file(tmpdir, f1)
            self._create_temp_file(tmpdir, f2)

            buf, count = _build_zip_archive([f1, f2])

            assert count == 2
            with zipfile.ZipFile(buf, "r") as zf:
                names = zf.namelist()
                assert len(names) == 2
                assert any("report.pdf" in n for n in names)
                assert any("notes.txt" in n for n in names)

    @patch(CONFIG_PATH)
    def test_archive_entry_names_use_id_prefix(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        fid = uuid.uuid4()
        f = make_file(
            file_name="doc.txt",
            file_path=f"{MOUNT_PATH}/x/doc.txt",
            file_id=fid,
        )

        with tempfile.TemporaryDirectory():
            os.makedirs(os.path.dirname(f.file_path), exist_ok=True)
            with open(f.file_path, "w") as fh:
                fh.write("hello")

            buf, count = _build_zip_archive([f])

        assert count == 1
        with zipfile.ZipFile(buf, "r") as zf:
            name = zf.namelist()[0]
            assert name == f"{str(fid)[:4]}_doc.txt"

    @patch(CONFIG_PATH)
    def test_skips_files_outside_mount_path(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_name="sneaky.txt", file_path="/etc/passwd")

        buf, count = _build_zip_archive([f])

        assert count == 0
        with zipfile.ZipFile(buf, "r") as zf:
            assert zf.namelist() == []

    @patch(CONFIG_PATH)
    def test_skips_files_not_on_disk(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_path=f"{MOUNT_PATH}/nonexistent/file.pdf")

        buf, count = _build_zip_archive([f])

        assert count == 0

    @patch(CONFIG_PATH)
    def test_skips_files_that_raise_on_write(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_name="bad.txt", file_path=f"{MOUNT_PATH}/c/bad.txt")

        os.makedirs(os.path.dirname(f.file_path), exist_ok=True)
        with open(f.file_path, "w") as fh:
            fh.write("content")

        with patch("zipfile.ZipFile.write", side_effect=OSError("disk error")):
            buf, count = _build_zip_archive([f])

        assert count == 0

    @patch(CONFIG_PATH)
    def test_empty_file_list_returns_empty_zip(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH

        buf, count = _build_zip_archive([])

        assert count == 0
        with zipfile.ZipFile(buf, "r") as zf:
            assert zf.namelist() == []

    @patch(CONFIG_PATH)
    def test_buffer_is_seeked_to_start(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH

        buf, _ = _build_zip_archive([])

        assert buf.tell() == 0

    @patch(CONFIG_PATH)
    def test_compressed_file_uses_stored(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_name="image.png", file_path=f"{MOUNT_PATH}/d/image.png")

        os.makedirs(os.path.dirname(f.file_path), exist_ok=True)
        with open(f.file_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)

        buf, count = _build_zip_archive([f])

        assert count == 1
        with zipfile.ZipFile(buf, "r") as zf:
            info = zf.infolist()[0]
            assert info.compress_type == zipfile.ZIP_STORED

    @patch(CONFIG_PATH)
    def test_text_file_uses_deflated(self, mock_config: MagicMock):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_name="notes.txt", file_path=f"{MOUNT_PATH}/e/notes.txt")

        os.makedirs(os.path.dirname(f.file_path), exist_ok=True)
        with open(f.file_path, "w") as fh:
            fh.write("some text content")

        buf, count = _build_zip_archive([f])

        assert count == 1
        with zipfile.ZipFile(buf, "r") as zf:
            info = zf.infolist()[0]
            assert info.compress_type == zipfile.ZIP_DEFLATED


# --- create_project_files_zip ---


class TestCreateProjectFilesZip:
    @pytest.mark.asyncio
    @patch(CONFIG_PATH)
    @patch(GET_FILES_PATH)
    async def test_returns_zip_with_files(
        self, mock_get_files: AsyncMock, mock_config: MagicMock
    ):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_name="doc.txt", file_path=f"{MOUNT_PATH}/f/doc.txt")
        os.makedirs(os.path.dirname(f.file_path), exist_ok=True)
        with open(f.file_path, "w") as fh:
            fh.write("hello world")

        mock_get_files.return_value = [f]

        buf, count = await create_project_files_zip(uuid.uuid4())

        assert count == 1
        assert isinstance(buf, io.BytesIO)
        with zipfile.ZipFile(buf, "r") as zf:
            assert len(zf.namelist()) == 1

    @pytest.mark.asyncio
    @patch(GET_FILES_PATH)
    async def test_raises_404_when_no_files(self, mock_get_files: AsyncMock):
        mock_get_files.return_value = []

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await create_project_files_zip(uuid.uuid4())
        assert exc_info.value.status_code == 404
        assert "No files found" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch(CONFIG_PATH)
    @patch(GET_FILES_PATH)
    async def test_raises_404_when_no_accessible_files(
        self, mock_get_files: AsyncMock, mock_config: MagicMock
    ):
        mock_config.FILE_UPLOADS_MOUNT_PATH = MOUNT_PATH
        f = make_file(file_path=f"{MOUNT_PATH}/missing/file.pdf")
        mock_get_files.return_value = [f]

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await create_project_files_zip(uuid.uuid4())
        assert exc_info.value.status_code == 404
        assert "No accessible files" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch(GET_FILES_PATH)
    async def test_default_roles_are_main_and_support(self, mock_get_files: AsyncMock):
        mock_get_files.return_value = []

        try:
            await create_project_files_zip(uuid.uuid4())
        except Exception:
            pass

        mock_get_files.assert_called_once()
        _, kwargs = mock_get_files.call_args
        assert set(kwargs["roles"]) == {FileRole.MAIN, FileRole.SUPPORT}

    @pytest.mark.asyncio
    @patch(GET_FILES_PATH)
    async def test_custom_roles_are_forwarded(self, mock_get_files: AsyncMock):
        mock_get_files.return_value = []

        try:
            await create_project_files_zip(
                uuid.uuid4(), roles=[FileRole.SUPPORTING_CANDIDATE]
            )
        except Exception:
            pass

        _, kwargs = mock_get_files.call_args
        assert kwargs["roles"] == [FileRole.SUPPORTING_CANDIDATE]
