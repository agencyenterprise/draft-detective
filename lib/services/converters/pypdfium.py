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

import pypdfium2 as pdfium  # type: ignore[import-untyped]

from lib.services.converters.base import FileConverterProtocol

logger = logging.getLogger(__name__)

_PDFIUM_LOCK = asyncio.Lock()

# PDFium emits Unicode noncharacters (U+FFFE, U+FFFF, U+FDD0..U+FDEF) at
# internal soft-hyphen and break boundaries inside word text. They survive as
# raw chars in get_text_range() output and break downstream substring matching
# (e.g. citation_validator's exact-quote search) — "complemen￾tary"
# won't match "complementary". Strip them post-extraction.
_NONCHARACTERS_RE = re.compile(r"[￾￿﷐-﷯]")


def _normalize(text: str) -> str:
    return _NONCHARACTERS_RE.sub("", text)


def _extract_text(file_path: str) -> str:
    pdf = pdfium.PdfDocument(file_path)
    try:
        chunks: list[str] = []
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            try:
                chunks.append(textpage.get_text_range())
            finally:
                textpage.close()
                page.close()
        return _normalize("\n\n".join(chunks))
    finally:
        pdf.close()


class PypdfiumFileConverter(FileConverterProtocol):
    async def convert_to_markdown(self, file_path: str) -> str:
        async with _PDFIUM_LOCK:
            return await asyncio.to_thread(_extract_text, file_path)


pypdfium_converter = PypdfiumFileConverter()
