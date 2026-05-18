import logging
from typing import Protocol

import aiofiles

logger = logging.getLogger(__name__)


class FileConverterProtocol(Protocol):

    async def convert_to_markdown(self, file_path: str) -> str: ...


async def convert_to_markdown(file_path: str, converter: str = "markitdown") -> str:
    """
    Convert a file to markdown using the specified converter.

    The 'pypdfium' converter is text-only (no tables/layout) but has a
    near-flat memory profile — used for supporting files where downstream
    agents only need textual content. 'markitdown' is the default and
    preserves more structure; used for the main document.
    """
    if file_path.lower().endswith((".md", ".markdown")):
        logger.info(f"File '{file_path}' is already markdown, reading directly")
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    logger.info(
        f"Converting file '{file_path}' to markdown using converter: '{converter}'"
    )

    if converter == "markitdown":
        from lib.services.converters.markitdown import markitdown_converter

        return await markitdown_converter.convert_to_markdown(file_path)

    if converter == "pypdfium":
        from lib.services.converters.pypdfium import pypdfium_converter

        return await pypdfium_converter.convert_to_markdown(file_path)

    raise ValueError(
        f"Invalid file converter: '{converter}'. "
        f"Supported converters: 'markitdown', 'pypdfium'."
    )
