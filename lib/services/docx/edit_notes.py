"""What a Word comment says about the proposed edits of its issue.

Every edit the export considered is written into the issue's comment, whether
or not it became a redline: an author reading the comment has to be able to see
the fix that was proposed, why, and -- when it is not in the margin as a
tracked change -- why not. A rejected edit is left out entirely; it was already
turned down.
"""

import uuid
from typing import List, Mapping, Optional, Sequence

from lib.models.issue_edit import IssueEdit
from lib.services.docx.tracked_changes import EditOutcome

_APPLIED = "Applied below as a tracked change."
_UNMATCHED = (
    "Not applied as a tracked change: the quoted text could not be matched "
    "in this paragraph."
)


def _unsupported_line(detail: Optional[str]) -> str:
    """Why a replacement has no redline of its own to offer."""
    reason = "the replacement cannot be represented in Word"
    aside = f" ({detail})" if detail else ""
    return f"Not applied as a tracked change: {reason}{aside}."


def _conflict_line(outcome: EditOutcome, winner_name: Optional[str]) -> str:
    """Where the edit it lost to sits: its own line, or the Word paragraph.

    A conflict the pre-flight decided names the winning edit, so it is the
    paragraph-wide case; one resolved before the document was opened is
    between two quotes of the same markdown line.
    """
    if winner_name:
        where = "in this paragraph" if outcome.winner_id else "on this line"
        return (
            "Not applied as a tracked change: overlaps another proposed edit "
            f"{where} ({winner_name})."
        )
    return (
        "Not applied as a tracked change: overlaps another proposed edit "
        "in the same paragraph."
    )


def _failed_line(detail: Optional[str]) -> str:
    """Why an edit that could be placed still has no redline.

    Distinct from the unmatched sentence on purpose: the quote was found, and
    what went wrong was the writing of the change.
    """
    reason = detail or "writing the change to Word failed"
    return f"Not applied as a tracked change: {reason}."


def _status_line(outcome: EditOutcome, winner_name: Optional[str]) -> str:
    if outcome.status == "applied":
        return _APPLIED
    if outcome.status == "conflict":
        return _conflict_line(outcome, winner_name)
    if outcome.status == "unsupported":
        return _unsupported_line(outcome.detail)
    if outcome.status == "failed":
        return _failed_line(outcome.detail)
    return _UNMATCHED


def _headline(edit: IssueEdit) -> str:
    if not edit.replacement_text:
        return f'Proposed deletion: "{edit.original_text}"'
    return f'Proposed edit: "{edit.original_text}" → "{edit.replacement_text}"'


def build_edit_notes(
    edits: Sequence[IssueEdit],
    outcomes: Mapping[uuid.UUID, EditOutcome],
    conflict_winner_names: Mapping[uuid.UUID, str],
) -> List[str]:
    """One comment block per edit of an issue, in the order proposed.

    `outcomes` is keyed by edit id; an edit with no outcome -- a rejected one,
    or one the export never considered -- contributes nothing.
    `conflict_winner_names` maps a losing edit's id to the display name of the
    workflow whose edit won, so the note can name what it lost to.
    """
    notes: List[str] = []
    for edit in edits:
        outcome = outcomes.get(edit.id)
        if outcome is None:
            continue
        notes.append(
            "\n".join(
                [
                    _headline(edit),
                    edit.rationale,
                    _status_line(outcome, conflict_winner_names.get(edit.id)),
                ]
            )
        )
    return notes
