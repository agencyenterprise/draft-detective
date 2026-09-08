"""Text of a document attached in the chat, via the same converter projects use.

The page used to extract attachments in a Next.js route with mammoth and unpdf.
Going through markitdown instead gives the agent the headings and tables the
workflows see, and keeps one conversion path for the whole product.
"""

import asyncio
import tempfile
from pathlib import Path

from lib.services.converters.base import convert_to_markdown

SUPPORTED_SUFFIXES = frozenset({".pdf", ".docx"})


class UnsupportedDocumentError(ValueError):
    """The file type is not one the chat accepts."""


class EmptyDocumentError(ValueError):
    """The file converted, but to nothing: a scanned PDF, or a blank document."""


async def extract_markdown(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedDocumentError("Only PDF and DOCX files are supported.")

    with tempfile.TemporaryDirectory(prefix="dd-chat-extract-") as directory:
        path = Path(directory) / f"upload{suffix}"
        await asyncio.to_thread(path.write_bytes, data)
        markdown = await convert_to_markdown(str(path), converter="markitdown")

    markdown = markdown.strip()
    if not markdown:
        raise EmptyDocumentError("No text could be extracted from the document.")
    return markdown
