"""PDFs that draw too many characters skip markitdown's pdfplumber reader.

pdfplumber holds about 2.7 KB per character, so a 1.4 KB crafted PDF drawing
400k characters took 1.28 GB. The tests build such PDFs in-process and stub
markitdown's reader, so they never pay that memory.
"""

import zlib
from pathlib import Path

import pytest
from markitdown import DocumentConverterResult

from lib.services.converters import markitdown as markitdown_module
from lib.services.converters.markitdown import markitdown_converter

_LINE_CHARS = 1000


def _write_text_pdf(path: Path, chars: int) -> Path:
    """A one-page PDF whose compressed content stream draws ``chars`` letters."""
    line = b"(" + b"a" * _LINE_CHARS + b") Tj 0 -1 Td\n"
    body = b"BT /F1 1 Tf 0 700 Td\n" + line * (chars // _LINE_CHARS) + b"ET\n"
    stream = zlib.compress(body, 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream)
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body_object in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body_object + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    path.write_bytes(pdf)
    return path


@pytest.fixture
def markitdown_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def fake_convert(path: str, **_kwargs: object) -> DocumentConverterResult:
        calls.append(path)
        return DocumentConverterResult(markdown="from markitdown")

    monkeypatch.setattr(
        markitdown_module.markitdown_converter.converter, "convert", fake_convert
    )
    return calls


@pytest.mark.asyncio
async def test_pdf_over_the_limit_converts_with_pypdfium(
    tmp_path: Path, markitdown_calls: list[str]
) -> None:
    # The size the bug was reported at: 1.8 KB of PDF, 1.86 GB through pdfplumber.
    chars = 600_000
    pdf = _write_text_pdf(tmp_path / "crafted.pdf", chars)
    assert pdf.stat().st_size < 4096

    markdown = await markitdown_converter.convert_to_markdown(str(pdf))

    assert markitdown_calls == []
    assert markdown.count("a") == chars


@pytest.mark.asyncio
async def test_bytes_before_the_header_do_not_bypass_the_limit(
    tmp_path: Path, markitdown_calls: list[str]
) -> None:
    # PDFium wants the header near the start, but pdfminer reads past a prefix.
    crafted = _write_text_pdf(tmp_path / "crafted.pdf", 600_000).read_bytes()
    pdf = tmp_path / "prefixed.pdf"
    pdf.write_bytes(b"x" * 2048 + crafted)

    markdown = await markitdown_converter.convert_to_markdown(str(pdf))

    assert markitdown_calls == []
    assert markdown.count("a") == 600_000


@pytest.mark.asyncio
async def test_header_at_the_end_of_the_window_is_found(
    tmp_path: Path, markitdown_calls: list[str]
) -> None:
    crafted = _write_text_pdf(tmp_path / "crafted.pdf", 600_000).read_bytes()
    # No .pdf name, and the header begins in the window's last byte.
    upload = tmp_path / "upload.bin"
    upload.write_bytes(b" " * 1023 + crafted)

    markdown = await markitdown_converter.convert_to_markdown(str(upload))

    assert markitdown_calls == []
    assert markdown.count("a") == 600_000


@pytest.mark.asyncio
async def test_pdf_pdfium_cannot_open_is_refused(
    tmp_path: Path, markitdown_calls: list[str]
) -> None:
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"not a pdf at all")

    with pytest.raises(ValueError, match="could not be read"):
        await markitdown_converter.convert_to_markdown(str(pdf))

    assert markitdown_calls == []


@pytest.mark.asyncio
async def test_pdf_under_the_limit_keeps_markitdown(
    tmp_path: Path, markitdown_calls: list[str]
) -> None:
    pdf = _write_text_pdf(tmp_path / "report.pdf", 10 * _LINE_CHARS)

    markdown = await markitdown_converter.convert_to_markdown(str(pdf))

    assert markitdown_calls == [str(pdf)]
    assert markdown == "from markitdown"
