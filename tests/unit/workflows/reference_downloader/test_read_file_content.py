"""read_file_content reads downloaded PDFs with pypdfium and reports unreadable files.

It reads only the run's own project's files.
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from lib.models.file import File
from lib.workflows.reference_downloader.tools import read_file_content as rfc

FILE_ID = "6f1c2a7e-0b8d-4c55-9a3e-2d4f6b8c0e11"
PROJECT_ID = "0d2b7e4a-5c61-4f0e-8a93-1b7c2d4e6f80"
OTHER_PROJECT_ID = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
TITLE = "Doctrine for the Armed Forces"


def _pdf_with_empty_inline_image_filter(text: str) -> bytes:
    """A one-page PDF whose content stream holds an inline image with `/F []`.

    pdfminer indexes the empty filter list and raises IndexError on it, which
    is what failed Joint Publication 1 in the reference downloader eval.
    """
    stream = (
        f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET\n"
        "q 10 0 0 10 72 600 cm BI /W 1 /H 1 /CS /G /BPC 8 /F [] ID \x00 EI Q\n"
    ).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def _file(path: Path, file_type: str, project_id: str = PROJECT_ID) -> MagicMock:
    file = MagicMock(spec=File)
    file.file_path = str(path)
    file.file_type = file_type
    file.project_id = uuid.UUID(project_id)
    return file


@pytest.mark.asyncio
async def test_reads_a_pdf_that_pdfminer_cannot_parse(tmp_path: Path) -> None:
    path = tmp_path / "jp1.pdf"
    path.write_bytes(_pdf_with_empty_inline_image_filter(TITLE))

    with patch.object(
        rfc, "get_file_by_id", AsyncMock(return_value=_file(path, "application/pdf"))
    ):
        content = await rfc._read_file_content_async(FILE_ID, PROJECT_ID)

    assert TITLE in content


@pytest.mark.asyncio
async def test_an_unreadable_file_returns_the_reason(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf")

    with patch.object(
        rfc, "get_file_by_id", AsyncMock(return_value=_file(path, "application/pdf"))
    ):
        content = await rfc._read_file_content_async(FILE_ID, PROJECT_ID)

    assert content.startswith(f"Could not read file {FILE_ID}")


@pytest.mark.asyncio
async def test_a_pdf_without_text_returns_the_reason(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(_pdf_with_empty_inline_image_filter(""))

    with patch.object(
        rfc, "get_file_by_id", AsyncMock(return_value=_file(path, "application/pdf"))
    ):
        content = await rfc._read_file_content_async(FILE_ID, PROJECT_ID)

    assert content.startswith(f"Could not read file {FILE_ID}")


@pytest.mark.asyncio
async def test_an_unknown_file_id_returns_the_reason() -> None:
    missing = HTTPException(status_code=404, detail="File not found")

    with patch.object(rfc, "get_file_by_id", AsyncMock(side_effect=missing)):
        content = await rfc._read_file_content_async(FILE_ID, PROJECT_ID)

    assert content.startswith(f"Could not read file {FILE_ID}")


@pytest.mark.asyncio
async def test_a_database_error_propagates() -> None:
    # Left to the agent's retry and the reference's ERROR status, not read as
    # an unreadable file the agent might conclude on.
    outage = OperationalError("SELECT", {}, Exception("connection refused"))

    with (
        patch.object(rfc, "get_file_by_id", AsyncMock(side_effect=outage)),
        pytest.raises(OperationalError),
    ):
        await rfc._read_file_content_async(FILE_ID, PROJECT_ID)


@pytest.mark.asyncio
async def test_a_file_of_another_project_reads_as_missing(tmp_path: Path) -> None:
    # The agent reads ids off web pages: one naming another project's file must
    # not return that file's text.
    path = tmp_path / "theirs.md"
    path.write_text("Another project's confidential draft")
    theirs = _file(path, "text/markdown", project_id=OTHER_PROJECT_ID)

    with patch.object(rfc, "get_file_by_id", AsyncMock(return_value=theirs)):
        content = await rfc._read_file_content_async(FILE_ID, PROJECT_ID)

    assert content == f"Could not read file {FILE_ID}: File not found"


@pytest.mark.asyncio
async def test_the_projects_id_reads_its_files_however_spelled(tmp_path: Path) -> None:
    path = tmp_path / "ours.md"
    path.write_text(TITLE)

    with patch.object(
        rfc, "get_file_by_id", AsyncMock(return_value=_file(path, "text/markdown"))
    ):
        content = await rfc._read_file_content_async(FILE_ID, PROJECT_ID.upper())

    assert content == TITLE
