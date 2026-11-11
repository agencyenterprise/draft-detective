"""PDF text extraction via pypdfium2.

Used in place of markitdown for PDFs because markitdown's PdfConverter loads
the entire document with pdfplumber, holding a per-character layout cache that
scales to ~100× the file size and triggers OOMs on academic batches.
pypdfium2 streams text from PDFium's existing text layer with a near-flat
memory profile (~50 MB peak across our 4-PDF reference batch vs ~2.5 GB for
markitdown).

PDFium is not thread-safe — concurrent calls from multiple threads corrupt
its internal global state. We serialize via a module-level asyncio.Lock so
non-PDF conversions can still run concurrently while PDFs go one at a time.
At ~175 ms/file even a 43-PDF batch finishes in ~7 s, so serializing is
effectively free compared to the previous behavior.
"""

import asyncio
import logging
import re
import threading
from pathlib import Path

import pypdfium2 as pdfium  # type: ignore[import-untyped]

from lib.services.converters.base import FileConverterProtocol

logger = logging.getLogger(__name__)

_PDFIUM_LOCK = asyncio.Lock()
# Cancelling an awaiting caller releases _PDFIUM_LOCK while its worker thread
# keeps running, so the workers also hold this lock for as long as they touch
# PDFium.
_PDFIUM_THREAD_LOCK = threading.Lock()

# Many pages can reuse one compressed content stream, so a few KB of PDF can
# hold any number of characters. Ten million is past a 3,000-page report.
MAX_PDF_TEXT_CHARS = 10_000_000


class PdfTextTooLargeError(ValueError):
    """The PDF holds more text than can be converted."""


# PDFium emits Unicode noncharacters (U+FFFE, U+FFFF, U+FDD0..U+FDEF) at
# internal soft-hyphen and break boundaries inside word text. They survive as
# raw chars in get_text_range() output and break downstream substring matching
# (e.g. citation_validator's exact-quote search) — "complemen￾tary"
# won't match "complementary". Strip them post-extraction.
_NONCHARACTERS_RE = re.compile(r"[￾￿﷐-﷯]")


def _normalize(text: str) -> str:
    return _NONCHARACTERS_RE.sub("", text)


def _open(file_path: str) -> pdfium.PdfDocument:
    """Open the PDF, also when bytes precede its ``%PDF-`` header.

    PDFium looks for the header only near the start of the file, while
    pdfminer reads past any prefix, so a prefixed file would otherwise be
    unreadable here yet readable by markitdown.
    """
    try:
        return pdfium.PdfDocument(file_path)
    except pdfium.PdfiumError:
        data = Path(file_path).read_bytes()
        start = data.find(b"%PDF-")
        if start <= 0:
            raise
        return pdfium.PdfDocument(data[start:])


def _extract_text(file_path: str) -> str:
    with _PDFIUM_THREAD_LOCK:
        return _extract_text_locked(file_path)


def _extract_text_locked(file_path: str) -> str:
    pdf = _open(file_path)
    try:
        chunks: list[str] = []
        total = 0
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            try:
                total += textpage.count_chars()
                if total > MAX_PDF_TEXT_CHARS:
                    raise PdfTextTooLargeError(
                        f"The PDF holds more than {MAX_PDF_TEXT_CHARS} "
                        "characters, more than can be converted."
                    )
                chunks.append(textpage.get_text_range())
            finally:
                textpage.close()
                page.close()
        return _normalize("\n\n".join(chunks))
    finally:
        pdf.close()


def _count_chars(file_path: str, stop_after: int) -> int:
    """Characters in the PDF's text layer, counting no further than ``stop_after``."""
    with _PDFIUM_THREAD_LOCK:
        return _count_chars_locked(file_path, stop_after)


def _count_chars_locked(file_path: str, stop_after: int) -> int:
    pdf = _open(file_path)
    try:
        total = 0
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            try:
                total += textpage.count_chars()
            finally:
                textpage.close()
                page.close()
            if total > stop_after:
                break
        return total
    finally:
        pdf.close()


async def count_pdf_chars(file_path: str, stop_after: int) -> int:
    """Count a PDF's characters with PDFium, cheaply and with flat memory.

    Stops once the count passes ``stop_after``, so callers comparing against a
    limit never pay for the rest of the document.
    """
    async with _PDFIUM_LOCK:
        return await asyncio.to_thread(_count_chars, file_path, stop_after)


class PypdfiumFileConverter(FileConverterProtocol):
    async def convert_to_markdown(self, file_path: str) -> str:
        async with _PDFIUM_LOCK:
            return await asyncio.to_thread(_extract_text, file_path)


pypdfium_converter = PypdfiumFileConverter()
