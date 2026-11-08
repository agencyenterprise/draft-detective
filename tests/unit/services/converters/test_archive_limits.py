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


def _docx(
    path: Path, padding: int = 0, media: int = 0, body_name: str = "document.xml"
) -> Path:
    """A real docx, its body padded with ``padding`` bytes of whitespace and an
    extra ``media`` bytes of zeros as a PNG: both deflate to almost nothing.
    ``body_name`` renames the main part, its relationships following."""
    source = path.with_suffix(".src.docx")
    document = docx.Document()
    document.add_paragraph("hello")
    document.save(str(source))
    with (
        zipfile.ZipFile(source) as src,
        zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for item in src.infolist():
            name, data = item.filename, src.read(item.filename)
            if name == "word/document.xml":
                name = f"word/{body_name}"
                data = data.replace(b"<w:body>", b"<w:body>" + b" " * padding)
            elif name == "word/_rels/document.xml.rels":
                name = f"word/_rels/{body_name}.rels"
            elif name in ("_rels/.rels", "[Content_Types].xml"):
                data = data.replace(b"document.xml", body_name.encode())
            dst.writestr(name, data)
        if media:
            dst.writestr("word/media/image1.png", b"\x89PNG" + b"\0" * media)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("body_name", ["document.dat", "media/image9.png"])
async def test_xml_cap_holds_for_a_renamed_body(
    tmp_path: Path, small_limits: None, body_name: str
):
    """Readers find the body through its relationships, not its name or folder."""
    bomb = _docx(tmp_path / "bomb.docx", padding=4 * _MIB, body_name=body_name)

    with pytest.raises(ArchiveTooLargeError):
        await markitdown_converter.convert_to_markdown(str(bomb))


def test_refuses_archive_expanding_past_upload_limit(
    tmp_path: Path, small_limits: None
):
    bomb = _docx(tmp_path / "bomb.docx", media=10 * _MIB)

    with (
        patch.object(archive_limits, "_may_be_xml") as inspect_part,
        pytest.raises(ArchiveTooLargeError),
    ):
        check_archive_expansion(str(bomb))
    inspect_part.assert_not_called()


def test_refuses_archive_with_too_many_parts(tmp_path: Path):
    archive = tmp_path / "parts.docx"
    with zipfile.ZipFile(archive, "w") as package:
        for index in range(11):
            package.writestr(f"word/part{index}.xml", b"<a/>")

    with (
        patch.object(archive_limits, "MAX_MEMBERS", 10),
        patch.object(archive_limits, "_may_be_xml") as inspect_part,
        pytest.raises(ArchiveTooLargeError),
    ):
        check_archive_expansion(str(archive))
    inspect_part.assert_not_called()


@pytest.mark.asyncio
async def test_honest_document_converts(tmp_path: Path, small_limits: None):
    document = _docx(tmp_path / "doc.docx", padding=256 * 1024, media=4 * _MIB)

    markdown = await markitdown_converter.convert_to_markdown(str(document))

    assert "hello" in markdown


def test_non_zip_files_pass(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"\0" * 1024)

    check_archive_expansion(str(pdf))
