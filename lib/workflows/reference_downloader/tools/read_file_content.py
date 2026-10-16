import logging

import aiofiles
from fastapi import HTTPException
from langchain.tools import ToolRuntime, tool

from lib.models.file import File
from lib.services.converters.markitdown import markitdown_converter
from lib.services.converters.pypdfium import pypdfium_converter
from lib.services.files.service import get_file_by_id
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 4000


@tool()
async def read_file_content(file_id: str, runtime: ToolRuntime[ContextSchema]):
    """
    Read the content of a file by its ID. Returns the content of the file in markdown format. Truncates the content to the first 4000 characters.

    Args:
        file_id: The ID of the file to read the content from.

    Returns:
        The first 4000 characters of the content of the file in markdown format, or a message saying why the file could not be read.
    """

    return await _read_file_content_async(file_id)


async def _read_file_content_async(file_id: str) -> str:
    # A file that cannot be read must not fail the whole reference: the agent
    # gets the reason back and can try another copy or conclude without it.
    # Other lookup errors (the database) still propagate, so the agent's retry
    # and the reference's ERROR status cover them.
    try:
        file = await get_file_by_id(file_id)
    except HTTPException as exc:
        logger.warning("read_file_content: no file %s: %s", file_id, exc.detail)
        return f"Could not read file {file_id}: {exc.detail}"

    try:
        content = await _file_to_markdown(file)
    except Exception as exc:
        logger.warning(
            "read_file_content: could not convert file %s (%s, %s): %s: %s",
            file_id,
            file.file_type,
            file.file_path,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return f"Could not read file {file_id}: {type(exc).__name__}: {exc}"

    total_chars = len(content) if content else 0
    if total_chars == 0:
        logger.warning(
            "read_file_content: file %s (%s, %s) produced no text",
            file_id,
            file.file_type,
            file.file_path,
        )
        return (
            f"Could not read file {file_id}: it has no extractable text "
            "(it may be a scanned image)"
        )

    logger.info(
        "read_file_content: file %s (%s) has %d chars, returning first %d",
        file_id,
        file.file_type,
        total_chars,
        min(total_chars, MAX_CONTENT_CHARS),
    )
    return content[:MAX_CONTENT_CHARS]


async def _file_to_markdown(file: File) -> str:
    if file.file_type == "text/markdown":
        # If file is already markdown, read directly from disk, no need to convert
        return await _read_file_directly(file.file_path)
    if file.file_type == "application/pdf":
        # pypdfium, as for every supporting PDF the app keeps, so the agent reads
        # the text the app will store. markitdown's pdfminer also crashes on some
        # PDFs (an inline image with an empty filter list raises IndexError).
        return await pypdfium_converter.convert_to_markdown(file.file_path)
    return await markitdown_converter.convert_to_markdown(file.file_path)


async def _read_file_directly(file_path: str) -> str:
    """Read file content directly from disk."""

    async with aiofiles.open(file_path, encoding="utf-8") as f:
        return await f.read()
