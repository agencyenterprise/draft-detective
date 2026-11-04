"""What a Word comment says about the proposed edits of its issue.

Every edit the export considered is noted in the issue's comment, whether or not
it became a redline. An applied edit is in the text as a tracked change, so its
note only points at the words that changed. One that is not in the text keeps
the whole fix, since the comment is then the only place it is, and says why it
is missing. A rejected edit is left out entirely; it was already turned down.
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel

from lib.models.issue_edit import IssueEdit
from lib.services.docx.edit_pointer import edit_fix, edit_pointer
from lib.services.docx.tracked_changes import EditOutcome

EditNoteStatus = Literal["applied", "skipped", "not_applied"]

_SKIPPED = "tracked changes were not requested for this export"
_UNMATCHED = "the quoted text could not be matched in this paragraph"


class EditNote(BaseModel):
    """What a comment says about one proposed edit."""

    # "skipped": the export was asked for comments only, so no edit is applied.
    status: EditNoteStatus
    # The changed words, to match the comment to its redline.
    pointer: str
    # The whole edit, for a comment that is the only place it appears.
    fix: str
    rationale: str
    # Why the edit is not in the text as a tracked change; None when it is.
    reason: str | None = None


def _unsupported_reason(detail: str | None) -> str:
    """Why a replacement has no redline of its own to offer."""
    aside = f" ({detail})" if detail else ""
    return f"the replacement cannot be represented in Word{aside}"


def _conflict_reason(outcome: EditOutcome, winner_name: str | None) -> str:
    """Where the edit it lost to sits: its own line, or the Word paragraph.

    A conflict the pre-flight decided names the winning edit, so it is the
    paragraph-wide case; one resolved before the document was opened is
    between two quotes of the same markdown line.
    """
    if winner_name:
        where = "in this paragraph" if outcome.winner_id else "on this line"
        return f"overlaps another proposed edit {where} ({winner_name})"
    return "overlaps another proposed edit in the same paragraph"


def _reason(outcome: EditOutcome, winner_name: str | None) -> str | None:
    """Why the edit is not a redline, or None when it is one.

    A failed write is told apart from an unmatched quote on purpose: the quote
    was found, and what went wrong was the writing of the change.
    """
    if outcome.status == "applied":
        return None
    if outcome.status == "conflict":
        return _conflict_reason(outcome, winner_name)
    if outcome.status == "unsupported":
        return _unsupported_reason(outcome.detail)
    if outcome.status == "failed":
        return outcome.detail or "writing the change to Word failed"
    if outcome.status == "skipped":
        return _SKIPPED
    return _UNMATCHED


def _status(outcome: EditOutcome) -> EditNoteStatus:
    if outcome.status == "applied":
        return "applied"
    if outcome.status == "skipped":
        return "skipped"
    return "not_applied"


def build_edit_notes(
    edits: Sequence[IssueEdit],
    outcomes: Mapping[uuid.UUID, EditOutcome],
    conflict_winner_names: Mapping[uuid.UUID, str],
) -> list[EditNote]:
    """One note per edit of an issue, in the order proposed.

    `outcomes` is keyed by edit id; an edit with no outcome -- a rejected one,
    or one the export never considered -- contributes nothing.
    `conflict_winner_names` maps a losing edit's id to the display name of the
    workflow whose edit won, so the note can name what it lost to.
    """
    notes: list[EditNote] = []
    for edit in edits:
        outcome = outcomes.get(edit.id)
        if outcome is None:
            continue
        notes.append(
            EditNote(
                status=_status(outcome),
                pointer=edit_pointer(edit.original_text, edit.replacement_text),
                fix=edit_fix(edit.original_text, edit.replacement_text),
                rationale=edit.rationale,
                reason=_reason(outcome, conflict_winner_names.get(edit.id)),
            )
        )
    return notes
