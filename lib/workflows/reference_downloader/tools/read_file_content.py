import asyncio

import aiofiles
from langchain.tools import ToolRuntime, tool

from lib.services.converters.markitdown import markitdown_converter
from lib.services.files import get_file_by_id
from lib.workflows.context import ContextSchema


@tool()
def read_file_content(file_id: str, runtime: ToolRuntime[ContextSchema]):
    """
    Read the content of a file by its ID. Returns the content of the file in markdown format. Truncates the content to the first 4000 characters.

    Args:
        file_id: The ID of the file to read the content from.

    Returns:
        The first 4000 characters of the content of the file in markdown format.
    """

    return asyncio.run(_read_file_content_async(file_id))


async def _read_file_content_async(file_id: str) -> str | None:
    file = await get_file_by_id(file_id)
    if file is None:
        return None

    if file.file_type == "text/markdown":
        # If file is already markdown, read directly from disk, no need to convert
        content = await _read_file_directly(file.file_path)
        return content[:4000] if content else None

    # Use markitdown for conversion of non-markdown files
    markdown = await markitdown_converter.convert_to_markdown(file.file_path)
    return markdown[:4000]


async def _read_file_directly(file_path: str) -> str:
    """Read file content directly from disk."""

    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        return await f.read()
