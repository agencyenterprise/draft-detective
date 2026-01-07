from typing import Protocol
import logging
from lib.config.env import config

logger = logging.getLogger(__name__)


class FileConverterProtocol(Protocol):

    async def convert_to_markdown(self, file_path: str) -> str: ...


async def convert_to_markdown(file_path: str, converter: str = "markitdown") -> str:
    """
    Convert a file to markdown using the specified converter.

    Args:
        file_path: Path to the file to convert
        converter: The converter to use ('markitdown' or 'docling')

    Returns:
        Markdown string
    """
    if file_path.lower().endswith((".md", ".markdown")):
        logger.info(f"File '{file_path}' is already markdown, reading directly")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    logger.info(
        f"Converting file '{file_path}' to markdown using converter: '{converter}'"
    )

    if converter == "markitdown":
        from lib.services.converters.markitdown import markitdown_converter

        return await markitdown_converter.convert_to_markdown(file_path)

    elif converter == "docling":
        from lib.services.converters.docling import docling_converter

        return await docling_converter.convert_to_markdown(file_path)

    else:
        raise ValueError(f"Invalid file converter: {converter}")
