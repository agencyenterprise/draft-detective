import asyncio
import re

from markitdown import MarkItDown

from lib.services.converters.base import FileConverterProtocol

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
        self, file_path: str, keep_data_uris: bool = False
    ) -> str:
        # keep_data_uris=False truncates embedded images to a useless
        # `data:image/png;base64...` stub; True keeps the full payload so the
        # caller can extract the bytes. Either way the image stays on a single
        # markdown line, so line numbers are identical between the two modes.
        result = await asyncio.to_thread(
            self.converter.convert, file_path, keep_data_uris=keep_data_uris
        )
        return _fix_escaped_underscores_in_urls(result.markdown)


markitdown_converter = MarkitdownFileConverter()
