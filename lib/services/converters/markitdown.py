import asyncio
import re
from markitdown import MarkItDown

from lib.services.converters.base import FileConverterProtocol

_URL_ESCAPED_UNDERSCORE_RE = re.compile(r"(https?://\S+)")


def _fix_escaped_underscores_in_urls(markdown: str) -> str:
    """Markitdown escapes underscores inside URLs (e.g. foo\_bar). Restore them."""

    def _unescape(match: re.Match) -> str:
        return match.group(0).replace(r"\_", "_")

    return _URL_ESCAPED_UNDERSCORE_RE.sub(_unescape, markdown)


class MarkitdownFileConverter(FileConverterProtocol):
    def __init__(self):
        self.converter = MarkItDown(enable_plugins=False)

    async def convert_to_markdown(self, file_path: str) -> str:
        result = await asyncio.to_thread(self.converter.convert, file_path)
        return _fix_escaped_underscores_in_urls(result.markdown)


markitdown_converter = MarkitdownFileConverter()
