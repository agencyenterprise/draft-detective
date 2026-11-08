"""A docx that expands past the limits is refused before any reader inflates it."""

import zipfile
from pathlib import Path
from unittest.mock import patch

import docx
import pytest

from lib.services.converters import archive_limits
from lib.services.converters.archive_limits import (
    ArchiveTooLargeError,
    check_archive_expansion,
)
from lib.services.converters.markitdown import markitdown_converter
from lib.services.files.conversion import convert_docx

_MIB = 1024 * 1024


def _docx(path: Path, padding: int = 0, media: int = 0) -> Path:
    """A real docx, its body padded with ``padding`` bytes of whitespace and an
    extra ``media`` bytes of zeros as a picture: both deflate to almost nothing."""
    source = path.with_suffix(".src.docx")
    document = docx.Document()
    document.add_paragraph("hello")
    document.save(str(source))
    with (
        zipfile.ZipFile(source) as src,
        zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = data.replace(b"<w:body>", b"<w:body>" + b" " * padding)
            dst.writestr(item.filename, data)
        if media:
            dst.writestr("word/media/image1.png", b"\0" * media)
    return path


@pytest.fixture
def small_limits():
    with (
        patch.object(archive_limits, "MAX_XML_BYTES", 2 * _MIB),
        patch.object(archive_limits, "MAX_EXPANDED_BYTES", 8 * _MIB),
    ):
        yield


@pytest.mark.asyncio
async def test_conversion_refuses_xml_bomb(tmp_path: Path, small_limits: None):
    bomb = _docx(tmp_path / "bomb.docx", padding=4 * _MIB)
    assert bomb.stat().st_size < 64 * 1024

    with (
        patch("lib.services.files.conversion.rasterize_docx_drawings") as rasterize,
        pytest.raises(ArchiveTooLargeError),
    ):
        await convert_docx(str(bomb), keep_data_uris=True)
    rasterize.assert_not_called()


@pytest.mark.asyncio
async def test_markitdown_refuses_xml_bomb(tmp_path: Path, small_limits: None):
    """Covers the routes that reach markitdown without ``convert_docx``."""
    bomb = _docx(tmp_path / "bomb.docx", padding=4 * _MIB)

    with pytest.raises(ArchiveTooLargeError):
        await markitdown_converter.convert_to_markdown(str(bomb))


def test_refuses_archive_expanding_past_upload_limit(
    tmp_path: Path, small_limits: None
):
    bomb = _docx(tmp_path / "bomb.docx", media=10 * _MIB)

    with pytest.raises(ArchiveTooLargeError):
        check_archive_expansion(str(bomb))


@pytest.mark.asyncio
async def test_honest_document_converts(tmp_path: Path, small_limits: None):
    document = _docx(tmp_path / "doc.docx", padding=256 * 1024, media=4 * _MIB)

    markdown = await markitdown_converter.convert_to_markdown(str(document))

    assert "hello" in markdown


def test_non_zip_files_pass(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"\0" * 1024)

    check_archive_expansion(str(pdf))
