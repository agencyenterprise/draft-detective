import asyncio
import logging
import mimetypes
import re

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from markitdown import DocumentConverterResult, MarkItDown, StreamInfo

from lib.services.converters.archive_limits import check_archive_expansion
from lib.services.converters.base import FileConverterProtocol
from lib.services.converters.docx_equations import convert_docx_equations
from lib.services.converters.pypdfium import count_pdf_chars, pypdfium_converter

logger = logging.getLogger(__name__)

_URL_ESCAPED_UNDERSCORE_RE = re.compile(r"(https?://\S+)")

# markitdown reads PDFs with pdfplumber, which keeps an object for every
# character it lays out: about 2.7 KB each, on real reports and crafted files
# alike (a 150-page report of 450k characters peaks at 1.26 GB). A PDF draws
# characters far more cheaply than that, so a few KB of upload could take more
# than the API pod's 2 GiB. Past this many characters a PDF goes through
# pypdfium instead: text only, without headings and tables, but flat memory.
MAX_MARKITDOWN_PDF_CHARS = 500_000

# A PDF's header may sit anywhere in its first kilobyte.
_PDF_HEADER_WINDOW = 1024
_PDF_MARKER = b"%PDF-"


def _is_pdf(file_path: str) -> bool:
    """Whether markitdown may read the file as a PDF: by its name or its header.

    The header settles only files whose name says nothing of their type, so a
    .txt that quotes ``%PDF-`` stays text.
    """
    if file_path.lower().endswith(".pdf"):
        return True
    if mimetypes.guess_type(file_path)[0] not in (None, "application/octet-stream"):
        return False
    with open(file_path, "rb") as f:
        # Read past the window by the marker's length, so a header starting
        # at its last byte is still whole.
        return _PDF_MARKER in f.read(_PDF_HEADER_WINDOW + len(_PDF_MARKER) - 1)


async def _too_many_chars_for_markitdown(file_path: str) -> bool:
    if not await asyncio.to_thread(_is_pdf, file_path):
        return False
    try:
        chars = await count_pdf_chars(file_path, stop_after=MAX_MARKITDOWN_PDF_CHARS)
    except pdfium.PdfiumError as error:
        # Without a count the file cannot go to pdfplumber, which a damaged
        # but still parseable PDF could hold to any size.
        raise ValueError("The PDF could not be read.") from error
    if chars <= MAX_MARKITDOWN_PDF_CHARS:
        return False
    logger.warning(
        "PDF %s draws more than %d characters; converting it with pypdfium "
        "instead of markitdown (text only, no headings or tables)",
        file_path,
        MAX_MARKITDOWN_PDF_CHARS,
    )
    return True


def _fix_escaped_underscores_in_urls(markdown: str) -> str:
    r"""Markitdown escapes underscores inside URLs (e.g. foo\_bar). Restore them."""

    def _unescape(match: re.Match) -> str:
        return match.group(0).replace(r"\_", "_")

    return _URL_ESCAPED_UNDERSCORE_RE.sub(_unescape, markdown)


class MarkitdownFileConverter(FileConverterProtocol):
    def __init__(self):
        self.converter = MarkItDown(enable_plugins=False)

    async def convert_to_markdown(
        self, file_path: str, keep_data_uris: bool = False, keep_equations: bool = True
    ) -> str:
        # keep_data_uris=False truncates embedded images to a useless
        # `data:image/png;base64...` stub; True keeps the full payload so the
        # caller can extract the bytes. Either way the image stays on a single
        # markdown line, so line numbers are identical between the two modes.
        # keep_equations=False leaves equations to MarkItDown alone, which drops
        # them all when one fails: only for matching markdown converted that way.
        if await _too_many_chars_for_markitdown(file_path):
            return await pypdfium_converter.convert_to_markdown(file_path)
        result = await asyncio.to_thread(
            self._convert, file_path, keep_data_uris, keep_equations
        )
        return _fix_escaped_underscores_in_urls(result.markdown)

    def _convert(
        self, file_path: str, keep_data_uris: bool, keep_equations: bool
    ) -> DocumentConverterResult:
        check_archive_expansion(file_path)
        if keep_equations and file_path.lower().endswith(".docx"):
            try:
                with_equations = convert_docx_equations(file_path)
            except Exception:
                logger.exception("Equation pre-processing failed for %s", file_path)
                with_equations = None
            if with_equations is not None:
                return self.converter.convert_stream(
                    with_equations,
                    stream_info=StreamInfo(extension=".docx"),
                    keep_data_uris=keep_data_uris,
                )
        return self.converter.convert(file_path, keep_data_uris=keep_data_uris)


markitdown_converter = MarkitdownFileConverter()
