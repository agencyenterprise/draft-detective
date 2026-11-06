"""What a redline pass hands back, and the workspace it needs to look.

The outcome of every proposed edit the export considered, the instructions for
the ones that became redlines, and the docx-editor workspace both passes open.
Shared by `planning` and `apply` so neither has
to import the other.
"""

import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal, Protocol

from pydantic import BaseModel

TRACKED_CHANGE_AUTHOR = "Draft Detective"


class LocatedQuoteLike(Protocol):
    """A quote located on one markdown line: an edit's, or an issue's passage.

    The fields the export reads to find the quote in a Word paragraph, as both
    `IssueEdit` and `IssuePassageRead` carry them.
    """

    original_text: str
    display_text: str
    display_occurrence: int
    start_line: int


EditOutcomeStatus = Literal[
    "applied",
    "conflict",
    "unlocatable",
    "not_found",
    "ambiguous",
    "unsupported",
    "failed",
    # The export was asked for comments only: the edit is described in its
    # issue's comment, and no redline was ever attempted for it.
    "skipped",
]


class EditOutcome(BaseModel):
    """What became of one proposed edit in the export.

    ``winner_id`` is set on a ``conflict`` the pre-flight itself decided -- two
    edits from different markdown lines landing on the same words of one Word
    paragraph -- and names the edit that was kept, so the comment can name the
    workflow it lost to the way a per-line conflict does.
    """

    edit_id: uuid.UUID
    status: EditOutcomeStatus
    detail: str | None = None
    winner_id: uuid.UUID | None = None


class PlannedEdit(BaseModel):
    """One redline, resolved to everything docx-editor needs to write it."""

    edit_id: uuid.UUID
    paragraph_ref: str
    paragraph_index: int
    find: str
    replace_with: str
    occurrence: int
    # Where `find` sits in the paragraph's text. Used to order the operations of
    # one paragraph back-to-front and to refuse two that touch the same words.
    span: tuple[int, int]


class TrackedChangesPlan(BaseModel):
    """The redlines to write, plus what to say about every edit considered.

    `outcomes` covers each decision except rejected edits, which the export
    leaves out entirely. An edit the pre-flight can place is reported as
    ``applied`` here; if the write then refuses it, the caller notes it as
    failed and writes the file again without it (see
    `lib.services.docx.edit_export`), so no delivered comment claims it.
    """

    planned: list[PlannedEdit]
    outcomes: list[EditOutcome]


@contextmanager
def editor_workspace(root: str | None) -> Iterator[str]:
    """A private docx-editor workspace, removed again afterwards.

    One per invocation so that two exports of the same document never contend
    for the same unpacked copy. Shared with the apply pass, which opens its own
    while it writes.
    """
    path = tempfile.mkdtemp(prefix="docx-editor-", dir=root)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
