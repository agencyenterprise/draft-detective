"""Resolving the applicable proposed edits to redlines, without writing any.

A read-only pre-flight against the *original* file. Each edit is mapped to a
Word paragraph by its markdown line and handed to
`tracked_changes_placement.plan_edit`; what comes back is either a redline to
write or an outcome saying why it cannot be one. Then the paragraph's own
overlaps are settled, since one paragraph can cover several markdown lines and
two edits that never competed on a line can still cover the same words.

Nothing here writes; `tracked_changes_apply` does that, and takes this
module's `PlannedEdit` rows as its instructions.
"""

import asyncio
import uuid
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from docx import Document as PythonDocxDocument
from docx_editor import Document as EditorDocument

from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.services.docx.paragraph_refs import (
    MappedParagraph,
    map_paragraph_refs,
    paragraph_ordinals,
)
from lib.services.docx.tracked_changes_models import (
    TRACKED_CHANGE_AUTHOR,
    EditOutcome,
    PlannedEdit,
    TrackedChangesPlan,
    editor_workspace,
)
from lib.services.docx.tracked_changes_placement import plan_edit
from lib.services.edit_conflicts import EditCandidate, EditDecision, pick_winner

# Why nothing could be placed: python-docx and docx-editor disagreed on the
# document's paragraphs, so not one ref could be trusted.
_UNMAPPABLE_DOCUMENT = (
    "the document's paragraphs could not be matched to the file being exported"
)


def _paragraph_map(
    docx_path: str, workspace_root: Optional[str]
) -> Optional[Dict[int, MappedParagraph]]:
    """``{python-docx paragraph index: docx-editor paragraph}`` for a file.

    ``None`` when the two libraries do not agree on the document's paragraphs;
    see `map_paragraph_refs`. Nothing may be redlined in that case.
    """
    with editor_workspace(workspace_root) as workspace:
        doc = EditorDocument.open(
            docx_path, author=TRACKED_CHANGE_AUTHOR, workspace_dir=workspace
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


def _paragraph_overlap_groups(
    planned: Sequence[PlannedEdit],
) -> List[List[PlannedEdit]]:
    """Group the redlines of one Word paragraph that cover the same characters.

    Conflicts were resolved per markdown line, but one Word paragraph can cover
    several lines (a list, a table row, a hard line break), so two edits from
    different lines can still land on the same words. They must not both reach
    docx-editor: an operation whose search text overlaps text an earlier
    operation inserted corrupts the paragraph silently.

    Overlap is transitive, the way it is within a line: walking a paragraph's
    spans in start order closes a group as soon as a span starts at or after
    the furthest end reached so far.
    """
    by_paragraph: Dict[str, List[PlannedEdit]] = {}
    for edit in planned:
        by_paragraph.setdefault(edit.paragraph_ref, []).append(edit)

    groups: List[List[PlannedEdit]] = []
    for ref in sorted(by_paragraph):
        ordered = sorted(
            by_paragraph[ref], key=lambda edit: (edit.span, str(edit.edit_id))
        )
        current: List[PlannedEdit] = []
        reach = -1
        for edit in ordered:
            if current and edit.span[0] < reach:
                current.append(edit)
                reach = max(reach, edit.span[1])
                continue
            if current:
                groups.append(current)
            current = [edit]
            reach = edit.span[1]
        if current:
            groups.append(current)
    return groups


def _resolve_paragraph_overlaps(
    planned: Sequence[PlannedEdit],
    candidates_by_id: Mapping[uuid.UUID, EditCandidate],
) -> Tuple[List[PlannedEdit], List[EditOutcome]]:
    """Keep one redline per overlap group, by the same policy as a line's.

    The winner is `pick_winner`'s, not whichever edit happened to be planned
    first: an accepted edit beats a proposed one here exactly as it does when
    both quotes sit on the same markdown line.
    """
    kept: List[PlannedEdit] = []
    losses: List[EditOutcome] = []
    for group in _paragraph_overlap_groups(planned):
        if len(group) == 1:
            kept.append(group[0])
            continue
        winner_id = pick_winner(
            [candidates_by_id[edit.edit_id] for edit in group]
        ).edit.id
        for edit in group:
            if edit.edit_id == winner_id:
                kept.append(edit)
                continue
            losses.append(
                EditOutcome(
                    edit_id=edit.edit_id,
                    status="conflict",
                    detail=f"overlaps proposed edit {winner_id} in this paragraph",
                    winner_id=winner_id,
                )
            )
    return kept, losses


def _plan_sync(
    docx_path: str,
    decisions: Sequence[EditDecision],
    candidates_by_id: Mapping[uuid.UUID, EditCandidate],
    paragraph_line_ranges: Dict[int, Tuple[int, int]],
    document_lines: Sequence[str],
    workspace_root: Optional[str],
) -> TrackedChangesPlan:
    applicable = [d for d in decisions if d.outcome == "apply"]
    outcomes: List[EditOutcome] = [
        EditOutcome(
            edit_id=decision.edit_id,
            status="conflict" if decision.outcome == "conflict" else "unlocatable",
        )
        for decision in decisions
        if decision.outcome in ("conflict", "unlocatable")
    ]
    if not applicable:
        return TrackedChangesPlan(planned=[], outcomes=outcomes)

    paragraphs = _paragraph_map(docx_path, workspace_root)
    if paragraphs is None:
        # The file's paragraphs could not be tied to docx-editor's, so no ref
        # is trustworthy. Every edit is reported rather than written blind.
        return TrackedChangesPlan(
            planned=[],
            outcomes=outcomes
            + [
                EditOutcome(
                    edit_id=decision.edit_id,
                    status="not_found",
                    detail=_UNMAPPABLE_DOCUMENT,
                )
                for decision in applicable
            ],
        )

    planned: List[PlannedEdit] = []
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
        one, outcome = plan_edit(
            edit,
            paragraph_index,
            paragraph,
            paragraph_line_ranges[paragraph_index],
            document_lines,
        )
        if one is not None:
            planned.append(one)
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
    paragraph_line_ranges: Dict[int, Tuple[int, int]],
    document_lines: Sequence[str],
    workspace_root: Optional[str] = None,
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
