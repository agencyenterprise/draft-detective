"""Tool that lets a deep agent look at an image extracted from a document.

Persisted markdown references extracted images by a storage-agnostic
``draftdetective://{file-id}`` src (see ``lib/services/image_extraction``).
The document viewers resolve that scheme to the download endpoint; agents
resolve it here — the tool returns the image bytes as a standard image
content block, which the model reads directly from the tool result.
"""

import base64
import logging
import uuid
from collections.abc import Sequence
from typing import Any

import aiofiles
from fastapi import HTTPException
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import BaseMessage, ToolMessage

from lib.models.file import FileRole
from lib.services.files.service import get_file_by_id
from lib.services.image_extraction import IMAGE_REFERENCE_SCHEME
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

# Formats the vision models accept. Anything else (metafiles that skipped
# rasterization, SVG, ...) gets a text explanation instead of bytes the model
# would reject.
VIEWABLE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})

# One oversized image must not crowd out the rest of the agent's context.
MAX_IMAGE_BYTES = 15 * 1024 * 1024

_NOT_FOUND = (
    "Error: no document image exists for this reference in the current project."
)

# Appended to the system prompt of every agent that binds `view_image`, so the
# instructions always travel with the tool. Skills stay environment-agnostic
# (see CLAUDE.md, "Skill Files"): this runtime-specific wiring lives here, next
# to the tool, and each skill only says *when* a look is worth taking.
VIEW_IMAGE_PROMPT = """

## Document Images

Images extracted from a document appear in its markdown as \
`![alt](draftdetective://...)`. Pass such a `draftdetective://...` src to the \
`view_image` tool to look at the image itself, whenever seeing it would change \
your judgment. If the tool reports that an image cannot be displayed, judge it \
from its alt text and the surrounding text instead.\
"""


def _parse_image_file_id(image_reference: str) -> uuid.UUID | None:
    """The file id inside a reference; None when it isn't one.

    Accepts the full ``draftdetective://{id}?w=&h=`` form the markdown carries
    as well as a bare id, so the model can pass either.
    """
    reference = image_reference.strip()
    if reference.startswith(IMAGE_REFERENCE_SCHEME):
        reference = reference[len(IMAGE_REFERENCE_SCHEME) :]
    reference = reference.split("?", 1)[0]
    try:
        return uuid.UUID(reference)
    except ValueError:
        return None


@tool()
async def view_image(
    image_reference: str, runtime: ToolRuntime[ContextSchema]
) -> list[dict[str, Any]] | str:
    """
    Look at an image embedded in a document. Images appear in the document
    markdown as `![alt](draftdetective://...)`; pass that `draftdetective://...`
    src (query parameters and all) to see the image itself.

    Args:
        image_reference: The image src from the document markdown, e.g.
            `draftdetective://123e4567-e89b-12d3-a456-426614174000?w=400&h=300`.

    Returns:
        The image as visual content, or an error message when the reference
        does not resolve to a viewable image.
    """
    file_id = _parse_image_file_id(image_reference)
    if file_id is None:
        return (
            f"Error: {image_reference!r} is not an image reference. Pass the "
            f"`{IMAGE_REFERENCE_SCHEME}...` src of a markdown image in the document."
        )

    try:
        file = await get_file_by_id(file_id)
    except HTTPException:
        # A missing row is the expected miss for a guessed or stale id.
        return _NOT_FOUND
    except Exception:
        # The model still gets the not-found message, so it cannot tell a
        # missing file from an outage; the log can.
        logger.warning("Could not look up document image %s", file_id, exc_info=True)
        return _NOT_FOUND

    # Scope to the running project's extracted images: the id comes from model
    # output, so it must not be able to read arbitrary files by guessing ids.
    if (
        str(file.project_id) != str(runtime.context.project_id)
        or file.role != FileRole.EXTRACTED_IMAGE
    ):
        return _NOT_FOUND

    if file.file_type not in VIEWABLE_MIME_TYPES:
        return (
            f"This image is stored as {file.file_type}, which cannot be displayed. "
            "Judge it from its alt text and surrounding document context instead."
        )
    if file.file_size > MAX_IMAGE_BYTES:
        return (
            "This image is too large to display. Judge it from its alt text "
            "and surrounding document context instead."
        )

    try:
        async with aiofiles.open(file.file_path, "rb") as f:
            # Bounded read: the metadata check above is only a hint, and the
            # cap must hold even if the row and the file on disk disagree.
            content = await f.read(MAX_IMAGE_BYTES + 1)
    except OSError:
        logger.warning(
            "Extracted image %s is missing from disk at %s", file.id, file.file_path
        )
        return (
            "Error: the image file is missing from storage. Judge it from its "
            "alt text and surrounding document context instead."
        )
    if len(content) > MAX_IMAGE_BYTES:
        return (
            "This image is too large to display. Judge it from its alt text "
            "and surrounding document context instead."
        )

    return [
        {
            "type": "image",
            "source_type": "base64",
            "data": base64.b64encode(content).decode(),
            "mime_type": file.file_type,
        }
    ]


def redact_image_blocks(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """The messages with every image block in a tool result replaced by a note.

    A viewed image reaches the model as base64 inside a ``ToolMessage``. Left
    there, it is persisted with the run's transcript (the workflow's
    ``state_json``) and served back with the run detail: tens of megabytes for
    a document with a few figures. The note keeps the transcript readable (the
    agent looked at this image, this big) without the bytes.
    """
    redacted: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, ToolMessage) and isinstance(message.content, list):
            blocks = [_redact_block(block) for block in message.content]
            if blocks != list(message.content):
                message = message.model_copy(update={"content": blocks})
        redacted.append(message)
    return redacted


def _redact_block(block: Any) -> Any:
    if not (isinstance(block, dict) and block.get("type") == "image"):
        return block
    encoded = block.get("data") or block.get("base64") or ""
    size_kb = len(encoded) * 3 // 4 // 1024
    return {
        "type": "text",
        "text": (
            f"[image {block.get('mime_type', '')}, {size_kb} KB; "
            "bytes omitted from the stored transcript]"
        ),
    }
