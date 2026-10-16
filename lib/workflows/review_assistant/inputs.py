"""Mount a review request's documents on the agent filesystem.

Each document gets its own folder under ``/inputs/``, numbered in the order the
author gave them:

- ``document.md``: the document's text, as converted from the upload
- ``comments.md``: its Word comment threads, when it is a DOCX that has any
- ``tracked-changes.md``: its tracked insertions and deletions, likewise

``/inputs/index.md`` lists every folder with what the upload itself says (file
name, the DOCX's author and dates, how many comments and changes it carries),
which is the agent's starting point for working out what each document is.
"""

import asyncio
import logging
import re
from typing import Any

from deepagents.backends.utils import create_file_data
from pydantic import BaseModel, Field

from lib.services.docx.review_markup import DocxReviewMarkup, read_docx_review_markup
from lib.services.docx.review_markup_markdown import (
    comments_markdown,
    tracked_changes_markdown,
    visible_changes,
)
from lib.services.files.document import FileDocument
from lib.workflows.review_assistant.state import ReviewAssistantInput

logger = logging.getLogger(__name__)

INPUTS_ROOT = "/inputs"
INPUTS_INDEX_PATH = f"{INPUTS_ROOT}/index.md"


class MountedInputs(BaseModel):
    inputs: list[ReviewAssistantInput]
    files: dict[str, Any]
    markup_warnings: list[str] = Field(
        default_factory=list,
        description="Documents whose comments and tracked changes were not read",
    )


class _Markup(BaseModel):
    """What a document's review markup reading gave: the markup, or why not."""

    markup: DocxReviewMarkup | None = None
    not_read: str | None = None


def _slug(file_name: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", file_name)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return slug[:60] or "document"


def _has_extension(document: FileDocument, extension: str) -> bool:
    return any(
        name.lower().endswith(extension)
        for name in (document.file_name, document.file_path)
    )


async def _read_markup(document: FileDocument) -> _Markup:
    """The DOCX's comments and tracked changes, or why they could not be read.

    A file that will not parse loses only its markup: its text is still read.
    Its feedback may live only in that markup, though, so the loss is reported
    rather than read as a document without comments.
    """
    if _has_extension(document, ".doc"):
        return _Markup(
            not_read=(
                f"{document.file_name} is a legacy Word (.doc) file, so its comments "
                "and tracked changes were not read, only its text. Save it as .docx "
                "to include them."
            )
        )
    if not _has_extension(document, ".docx"):
        return _Markup()
    try:
        markup = await asyncio.to_thread(read_docx_review_markup, document.file_path)
    except Exception as error:
        logger.warning("Could not read comments from %s: %s", document.file_name, error)
        return _Markup(
            not_read=(
                f"Could not read the comments and tracked changes in "
                f"{document.file_name} ({error}), only its text."
            )
        )
    return _Markup(markup=markup)


def _index_entry(entry: ReviewAssistantInput, read: _Markup) -> str:
    lines = [f"## {entry.folder}", "", f"- File name: {entry.file_name}"]
    markup = read.markup
    if markup is not None:
        properties = markup.properties
        for label, value in (
            ("Author (file properties)", properties.author),
            ("Last saved by", properties.last_modified_by),
            ("Created", properties.created),
            ("Last modified", properties.modified),
        ):
            if value:
                lines.append(f"- {label}: {value}")
    lines.append(f"- Text: `{entry.folder}/document.md`")
    if entry.comment_count:
        lines.append(
            f"- Comments: {entry.comment_count} thread(s), in `{entry.folder}/comments.md`"
        )
    if entry.tracked_change_count:
        lines.append(
            f"- Tracked changes: {entry.tracked_change_count}, in "
            f"`{entry.folder}/tracked-changes.md`"
        )
    if read.not_read:
        lines.append(
            f"- Comments and tracked changes: not read. {read.not_read} Any "
            "feedback left only as comments or tracked changes is missing; say so "
            "in your outputs rather than treat the document as unmarked."
        )
    return "\n".join(lines)


async def mount_review_inputs(documents: list[FileDocument]) -> MountedInputs:
    """Build the ``/inputs/`` tree for these documents."""
    files: dict[str, Any] = {}
    inputs: list[ReviewAssistantInput] = []
    index_entries: list[str] = []
    markup_warnings: list[str] = []

    for number, document in enumerate(documents, start=1):
        folder = f"{INPUTS_ROOT}/{number:02d}-{_slug(document.file_name)}"
        files[f"{folder}/document.md"] = create_file_data(document.markdown)

        read = await _read_markup(document)
        markup = read.markup
        if read.not_read:
            markup_warnings.append(read.not_read)
        comments = comments_markdown(document.file_name, markup) if markup else None
        changes = (
            tracked_changes_markdown(document.file_name, markup) if markup else None
        )
        if comments:
            files[f"{folder}/comments.md"] = create_file_data(comments)
        if changes:
            files[f"{folder}/tracked-changes.md"] = create_file_data(changes)

        entry = ReviewAssistantInput(
            file_id=document.file_id,
            file_name=document.file_name,
            folder=folder,
            comment_count=len(markup.comments) if markup else 0,
            tracked_change_count=len(visible_changes(markup)) if markup else 0,
        )
        inputs.append(entry)
        index_entries.append(_index_entry(entry, read))

    index = "\n\n".join(
        [
            "# Inputs",
            f"{len(inputs)} document(s), in the order the author gave them. "
            "Nobody has said what each one is: work that out from its content.",
            *index_entries,
        ]
    )
    files[INPUTS_INDEX_PATH] = create_file_data(index + "\n")
    return MountedInputs(inputs=inputs, files=files, markup_warnings=markup_warnings)
