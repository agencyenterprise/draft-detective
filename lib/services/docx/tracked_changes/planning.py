"""Resolving the applicable proposed edits to redlines, without writing any.

A read-only pre-flight against the *original* file. Each edit is mapped to a
Word paragraph by its markdown line and handed to
`placement.plan_edit`; what comes back is either a redline to
write or an outcome saying why it cannot be one. Then the paragraph's own
overlaps are settled, since one paragraph can cover several markdown lines and
two edits that never competed on a line can still cover the same words.

Nothing here writes; `apply` does that, and takes this
module's `PlannedEdit` rows as its instructions.
"""

import asyncio
import shutil
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

from docx import Document as PythonDocxDocument
from docx_editor import Document as EditorDocument

from lib.services.docx.edit_conflicts import (
    EditCandidate,
    EditDecision,
    overlap_groups,
    pick_winner,
)
from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.services.docx.paragraph_refs import (
    MappedParagraph,
    map_paragraph_refs,
    paragraph_ordinals,
)
from lib.services.docx.tracked_changes.models import (
    TRACKED_CHANGE_AUTHOR,
    EditOutcome,
    PlannedEdit,
    TrackedChangesPlan,
    editor_workspace,
)
from lib.services.docx.tracked_changes.placement import plan_edit

# Why nothing could be placed: python-docx and docx-editor disagreed on the
# document's paragraphs, so not one ref could be trusted.
_UNMAPPABLE_DOCUMENT = (
    "the document's paragraphs could not be matched to the file being exported"
)


def _docx_named(docx_path: str, directory: str) -> str:
    """The file under a ``.docx`` name, copied into `directory` when it lacks one.

    docx-editor refuses any other extension, but an upload named ``.doc`` is
    often a Word 2007+ file underneath, and python-docx reads it as one.
    """
    if Path(docx_path).suffix.lower() == ".docx":
        return docx_path
    copy = Path(directory) / f"{Path(docx_path).stem}.docx"
    shutil.copyfile(docx_path, copy)
    return str(copy)


def _paragraph_map(
    docx_path: str, workspace_root: str | None
) -> dict[int, MappedParagraph] | None:
    """``{python-docx paragraph index: docx-editor paragraph}`` for a file.

    ``None`` when the two libraries do not agree on the document's paragraphs;
    see `map_paragraph_refs`. Nothing may be redlined in that case.
    """
    with (
        editor_workspace(workspace_root) as workspace,
        editor_workspace(workspace_root) as copy_dir,
    ):
        doc = EditorDocument.open(
            _docx_named(docx_path, copy_dir),
            author=TRACKED_CHANGE_AUTHOR,
            workspace_dir=workspace,
        )
        try:
            editor_paragraphs = doc.list_paragraphs_structured(limit=None)
        finally:
            doc.close()
    walk = paragraph_ordinals(PythonDocxDocument(docx_path))
    if walk is None:
        return None
    ordinals, total = walk
    return map_paragraph_refs(ordinals, total, editor_paragraphs)


def _decided_outcomes(decisions: Sequence[EditDecision]) -> list[EditOutcome]:
    """Outcomes for the edits the per-line resolution already ruled out."""
    return [
        EditOutcome(
            edit_id=decision.edit_id,
            status="conflict" if decision.outcome == "conflict" else "unlocatable",
        )
        for decision in decisions
        if decision.outcome in ("conflict", "unlocatable")
    ]


def unplaceable_outcomes(
    decisions: Sequence[EditDecision], detail: str | None = None
) -> list[EditOutcome]:
    """Outcomes for when no edit can be tied to a Word paragraph at all.

    Every edit that would otherwise apply is reported as ``not_found``, with
    `detail` saying why; the rest keep the per-line resolution's verdict.
    Rejected edits are left out, as everywhere else.
    """
    return _decided_outcomes(decisions) + [
        EditOutcome(edit_id=decision.edit_id, status="not_found", detail=detail)
        for decision in decisions
        if decision.outcome == "apply"
    ]


def _resolve_paragraph_overlaps(
    planned: Sequence[PlannedEdit],
    candidates_by_id: Mapping[uuid.UUID, EditCandidate],
) -> tuple[list[PlannedEdit], list[EditOutcome]]:
    """Keep one edit per overlap group, by the same policy as a line's.

    The winner is `pick_winner`'s, not whichever edit happened to be planned
    first: an accepted edit beats a proposed one here exactly as it does when
    both quotes sit on the same markdown line. An edit placed as several
    redlines (around footnote references) is kept or dropped whole, so a lost
    overlap on one of its redlines takes the others out too.
    """
    # One Word paragraph can cover several markdown lines (a list, a table row,
    # a hard line break), so two edits from different lines can still land on
    # the same words. They must not both reach docx-editor: an operation whose
    # search text overlaps text an earlier operation inserted corrupts the
    # paragraph silently.
    groups = overlap_groups(
        planned,
        key=lambda edit: edit.paragraph_ref,
        span=lambda edit: edit.span,
        item_id=lambda edit: f"{edit.edit_id}:{edit.span}",
    )
    winners: dict[uuid.UUID, uuid.UUID] = {}
    for group in groups:
        edit_ids = list(dict.fromkeys(edit.edit_id for edit in group))
        if len(edit_ids) == 1:
            continue
        winner_id = pick_winner([candidates_by_id[i] for i in edit_ids]).edit.id
        for edit_id in edit_ids:
            if edit_id != winner_id:
                winners.setdefault(edit_id, winner_id)
    losses = [
        EditOutcome(
            edit_id=edit_id,
            status="conflict",
            detail=f"overlaps proposed edit {winner_id} in this paragraph",
            winner_id=winner_id,
        )
        for edit_id, winner_id in winners.items()
    ]
    return [edit for edit in planned if edit.edit_id not in winners], losses


def _plan_sync(
    docx_path: str,
    decisions: Sequence[EditDecision],
    candidates_by_id: Mapping[uuid.UUID, EditCandidate],
    paragraph_line_ranges: dict[int, tuple[int, int]],
    document_lines: Sequence[str],
    workspace_root: str | None,
) -> TrackedChangesPlan:
    applicable = [d for d in decisions if d.outcome == "apply"]
    outcomes = _decided_outcomes(decisions)
    if not applicable:
        return TrackedChangesPlan(planned=[], outcomes=outcomes)

    paragraphs = _paragraph_map(docx_path, workspace_root)
    if paragraphs is None:
        # The file's paragraphs could not be tied to docx-editor's, so no ref
        # is trustworthy. Every edit is reported rather than written blind.
        return TrackedChangesPlan(
            planned=[],
            outcomes=unplaceable_outcomes(decisions, _UNMAPPABLE_DOCUMENT),
        )

    planned: list[PlannedEdit] = []
    for decision in applicable:
        edit = candidates_by_id[decision.edit_id].edit
        paragraph_index = find_paragraph_by_line_range(
            paragraph_line_ranges, edit.start_line, edit.start_line
        )
        paragraph = (
            paragraphs.get(paragraph_index) if paragraph_index is not None else None
        )
        if paragraph_index is None or paragraph is None:
            outcomes.append(EditOutcome(edit_id=edit.id, status="not_found"))
            continue
        pieces, outcome = plan_edit(
            edit,
            paragraph_index,
            paragraph,
            paragraph_line_ranges[paragraph_index],
            document_lines,
        )
        planned.extend(pieces)
        outcomes.append(outcome)

    # Every applicable edit is planned first, then the paragraph's overlaps are
    # settled at once: the winner cannot be known while the group is still
    # being discovered.
    planned, losses = _resolve_paragraph_overlaps(planned, candidates_by_id)
    loss_by_id = {loss.edit_id: loss for loss in losses}
    return TrackedChangesPlan(
        planned=planned,
        outcomes=[loss_by_id.get(outcome.edit_id, outcome) for outcome in outcomes],
    )


async def plan_tracked_changes(
    docx_path: str,
    decisions: Sequence[EditDecision],
    candidates_by_id: Mapping[uuid.UUID, EditCandidate],
    paragraph_line_ranges: dict[int, tuple[int, int]],
    document_lines: Sequence[str],
    workspace_root: str | None = None,
) -> TrackedChangesPlan:
    """Resolve the applicable edits against `docx_path` without changing it.

    Runs against the original document so the comments can describe each edit's
    fate accurately. `document_lines` is the main document's markdown, split
    the way the edits were anchored. `candidates_by_id` carries the issue
    metadata for every decision, because two edits from different lines can
    still compete inside one Word paragraph and the winner is decided by the
    same policy that resolved the lines.
    """
    return await asyncio.to_thread(
        _plan_sync,
        docx_path,
        decisions,
        candidates_by_id,
        paragraph_line_ranges,
        document_lines,
        workspace_root,
    )
