import asyncio
import logging
import re

from markitdown import DocumentConverterResult, MarkItDown, StreamInfo

from lib.services.converters.base import FileConverterProtocol
from lib.services.converters.docx_equations import convert_docx_equations

logger = logging.getLogger(__name__)

_URL_ESCAPED_UNDERSCORE_RE = re.compile(r"(https?://\S+)")


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
        result = await asyncio.to_thread(
            self._convert, file_path, keep_data_uris, keep_equations
        )
        return _fix_escaped_underscores_in_urls(result.markdown)

    def _convert(
        self, file_path: str, keep_data_uris: bool, keep_equations: bool
    ) -> DocumentConverterResult:
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
