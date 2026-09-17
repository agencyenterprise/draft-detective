"""Deciding which proposed edits may be applied to the document at once.

Two workflows can propose edits that touch the same words: a reference checker
rewriting a citation inside a sentence an advocacy-tone check wants reworded.
Applying both would corrupt the passage -- and the redline library silently
corrupts a paragraph when one operation's search text overlaps text an earlier
operation inserted -- so overlapping edits have to be reduced to one winner
before anything is written.

The rules are pure and deterministic: given the same edits and the same
document, the same edit wins, whatever order the rows arrive in.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.services.docx.edit_text import locate_in_paragraph
from lib.workflows.models import SeverityEnum
from lib.workflows.simple_deep_agent.edit_anchoring import normalize_whitespace

EditOutcomeName = Literal["apply", "conflict", "unlocatable", "rejected"]


class EditCandidate(BaseModel):
    """One proposed edit, with the issue metadata the tie-breaks need."""

    edit: IssueEdit
    issue_severity: SeverityEnum
    issue_created_at: datetime
    workflow_type: str


class EditDecision(BaseModel):
    """What is to be done with one candidate edit.

    ``span`` is the ``[start, end)`` offset pair of the quote inside its
    markdown line, present whenever the quote could be located. ``apply``
    decisions list the other edits of their overlap group in
    ``conflicts_with`` too, so a caller can report what an edit beat.
    """

    edit_id: uuid.UUID
    line: int
    span: Optional[Tuple[int, int]]
    outcome: EditOutcomeName
    conflicts_with: List[uuid.UUID] = Field(default_factory=list)
    winner_id: Optional[uuid.UUID] = None


def _located_span(
    candidate: EditCandidate, document_lines: Sequence[str]
) -> Optional[Tuple[int, int]]:
    """The quote's span on its own markdown line, or None when it is not unique.

    A quote the line carries twice is as good as absent here: the edit cannot
    be tied to characters, so it is reported instead of guessed at.
    """
    line = candidate.edit.start_line
    if line < 1 or line > len(document_lines):
        return None
    spans = locate_in_paragraph(
        document_lines[line - 1], normalize_whitespace(candidate.edit.original_text)
    )
    return spans[0] if len(spans) == 1 else None


def winner_sort_key(candidate: EditCandidate) -> Tuple[int, int, float, str]:
    """Sort key picking the edit to keep: an accepted edit first, then the
    higher severity, then the older issue, then the lower id.

    The whole policy lives here so that every place two edits compete -- the
    per-line resolution below and the per-Word-paragraph pass the export runs
    once the lines have been mapped -- keeps the same edit, whatever order the
    rows arrived in.
    """
    created = candidate.issue_created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (
        0 if candidate.edit.status == IssueEditStatus.ACCEPTED else 1,
        -candidate.issue_severity.sort_index(),
        created.timestamp(),
        str(candidate.edit.id),
    )


def pick_winner(candidates: Sequence[EditCandidate]) -> EditCandidate:
    """The one edit of a competing group to keep, per `winner_sort_key`."""
    return min(candidates, key=winner_sort_key)


def _overlap_groups(
    located: Sequence[Tuple[EditCandidate, Tuple[int, int]]],
) -> List[List[EditCandidate]]:
    """Group edits that overlap, transitively, within one line.

    Walking the spans in start order is enough: a group is closed as soon as a
    span starts at or after the furthest end reached so far.
    """
    by_line: Dict[int, List[Tuple[EditCandidate, Tuple[int, int]]]] = {}
    for candidate, span in located:
        by_line.setdefault(candidate.edit.start_line, []).append((candidate, span))

    groups: List[List[EditCandidate]] = []
    for line in sorted(by_line):
        ordered = sorted(
            by_line[line], key=lambda pair: (pair[1], str(pair[0].edit.id))
        )
        current: List[EditCandidate] = []
        reach = -1
        for candidate, span in ordered:
            if current and span[0] < reach:
                current.append(candidate)
                reach = max(reach, span[1])
                continue
            if current:
                groups.append(current)
            current = [candidate]
            reach = span[1]
        if current:
            groups.append(current)
    return groups


def resolve_edit_conflicts(
    candidates: Sequence[EditCandidate], document_lines: Sequence[str]
) -> List[EditDecision]:
    """Decide, for every candidate, whether it can be applied to the document.

    Rejected edits are reported as such and never compete. An edit whose quote
    cannot be pinned to exactly one span of its line is ``unlocatable``. Of
    every group of edits whose spans overlap, one wins and the rest are
    ``conflict`` -- that includes duplicate proposals, which overlap exactly.

    Returned in line then span then id order, so the result does not depend on
    the order the rows came in.
    """
    decisions: List[EditDecision] = []
    located: List[Tuple[EditCandidate, Tuple[int, int]]] = []
    spans: Dict[uuid.UUID, Tuple[int, int]] = {}

    for candidate in candidates:
        edit = candidate.edit
        if edit.status == IssueEditStatus.REJECTED:
            decisions.append(
                EditDecision(
                    edit_id=edit.id, line=edit.start_line, span=None, outcome="rejected"
                )
            )
            continue
        span = _located_span(candidate, document_lines)
        if span is None:
            decisions.append(
                EditDecision(
                    edit_id=edit.id,
                    line=edit.start_line,
                    span=None,
                    outcome="unlocatable",
                )
            )
            continue
        spans[edit.id] = span
        located.append((candidate, span))

    for group in _overlap_groups(located):
        winner = pick_winner(group)
        member_ids = [member.edit.id for member in group]
        for member in group:
            others = [other_id for other_id in member_ids if other_id != member.edit.id]
            is_winner = member.edit.id == winner.edit.id
            decisions.append(
                EditDecision(
                    edit_id=member.edit.id,
                    line=member.edit.start_line,
                    span=spans[member.edit.id],
                    outcome="apply" if is_winner else "conflict",
                    conflicts_with=others,
                    winner_id=None if is_winner else winner.edit.id,
                )
            )

    return sorted(
        decisions,
        key=lambda decision: (
            decision.line,
            decision.span[0] if decision.span else -1,
            str(decision.edit_id),
        ),
    )
