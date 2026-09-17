"""The proposed-edit half of a DOCX export, from issue rows to redlines.

Sits between `generate_docx` and the passes it drives: conflict resolution over
the issues' proposed edits, the read-only pre-flight that resolves each
survivor to a paragraph, a rehearsal of the write on a throwaway copy, the
comment notes composed from the outcomes that rehearsal proved, and the apply
step that writes the redlines into the finished file.

The rehearsal is what keeps a comment honest. Comments have to be written
before the redlines -- python-docx stops reading inserted and deleted runs as
paragraph text, so the paragraph map the comment pass anchors to is only valid
beforehand -- and until the write has actually been attempted, nothing knows
whether docx-editor will take a given operation. So the write is attempted
twice: once against a scratch copy, whose outcomes decide what the comments say
and which edits are kept, and once for real.

`describe_edit_export` is the comments-only counterpart: an export that writes
no redlines still describes every edit in its issue's comment, and does so
without opening the document at all.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from lib.models.issue import Issue
from lib.models.issue_edit import IssueEditStatus
from lib.services.docx.edit_notes import build_edit_notes
from lib.services.docx.tracked_changes import (
    EditOutcome,
    PlannedEdit,
    apply_tracked_changes,
    plan_tracked_changes,
)
from lib.services.edit_conflicts import (
    EditCandidate,
    EditDecision,
    resolve_edit_conflicts,
)
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.simple_deep_agent.edit_anchoring import document_lines

logger = logging.getLogger(__name__)


class EditExport(BaseModel):
    """Everything the export still has to do about proposed edits."""

    planned: List[PlannedEdit] = Field(default_factory=list)
    outcomes: Dict[uuid.UUID, EditOutcome] = Field(default_factory=dict)
    notes_by_issue: Dict[uuid.UUID, List[str]] = Field(default_factory=dict)

    def notes_for(self, issue_id: uuid.UUID) -> List[str]:
        return self.notes_by_issue.get(issue_id, [])


def _workflow_name(issue: Issue) -> str:
    manifest = get_workflow_manifest(issue.workflow_type, raise_exception=False)
    return manifest.name if manifest else str(issue.workflow_type)


def _candidates(issues: Sequence[Issue]) -> List[EditCandidate]:
    return [
        EditCandidate(
            edit=row,
            issue_severity=issue.severity,
            issue_created_at=issue.created_at,
            workflow_type=str(issue.workflow_type),
        )
        for issue in issues
        for row in issue.edit_rows
    ]


def _unplaceable_outcomes(decisions: Sequence[EditDecision]) -> List[EditOutcome]:
    """Outcomes for the case where no paragraph mapping exists at all.

    The line-range mapper returns an empty map when the document converts
    differently than it did at ingestion. Nothing can be anchored then, so
    every edit that would otherwise apply is reported as unmatched.
    """
    outcomes: List[EditOutcome] = []
    for decision in decisions:
        if decision.outcome == "apply":
            outcomes.append(EditOutcome(edit_id=decision.edit_id, status="not_found"))
        elif decision.outcome == "conflict":
            outcomes.append(EditOutcome(edit_id=decision.edit_id, status="conflict"))
        elif decision.outcome == "unlocatable":
            outcomes.append(EditOutcome(edit_id=decision.edit_id, status="unlocatable"))
    return outcomes


def _notes(
    issues: Sequence[Issue],
    decisions: Sequence[EditDecision],
    outcomes: Dict[uuid.UUID, EditOutcome],
) -> Dict[uuid.UUID, List[str]]:
    """Comment blocks per issue, naming the workflow a conflict lost to.

    A conflict is decided either per markdown line, before the document is
    opened, or per Word paragraph by the pre-flight; the winner's id comes off
    the decision in the first case and off the outcome in the second, and both
    resolve to a workflow name the same way.
    """
    issue_of_edit: Dict[uuid.UUID, Issue] = {
        row.id: issue for issue in issues for row in issue.edit_rows
    }
    winner_ids: Dict[uuid.UUID, uuid.UUID] = {
        decision.edit_id: decision.winner_id
        for decision in decisions
        if decision.winner_id is not None
    }
    winner_ids.update(
        {
            outcome.edit_id: outcome.winner_id
            for outcome in outcomes.values()
            if outcome.winner_id is not None
        }
    )
    winner_names: Dict[uuid.UUID, str] = {}
    for edit_id, winner_id in winner_ids.items():
        winner = issue_of_edit.get(winner_id)
        if winner is not None:
            winner_names[edit_id] = _workflow_name(winner)
    return {
        issue.id: notes
        for issue in issues
        if (notes := build_edit_notes(issue.edit_rows, outcomes, winner_names))
    }


async def _rehearse(
    docx_path: str, planned: Sequence[PlannedEdit], workspace_root: Optional[str]
) -> List[EditOutcome]:
    """Apply the plan to a throwaway copy of the original and report what stuck.

    docx-editor is deterministic: the same operations against the same
    paragraphs of the same document produce the same result, and the plan's
    refs are anchored to a hash of each paragraph's visible text, which the
    comment pass does not change. So what fails here is what would fail on the
    exported file, and what applies here applies there -- `apply_edit_export`
    logs it if that ever stops holding.

    The copy is deleted again; nothing in it is kept but the outcomes.
    """
    scratch_dir = await asyncio.to_thread(
        tempfile.mkdtemp, prefix="edit-rehearsal-", dir=workspace_root
    )
    try:
        scratch = os.path.join(scratch_dir, "rehearsal.docx")
        await asyncio.to_thread(shutil.copyfile, docx_path, scratch)
        return await apply_tracked_changes(
            scratch, planned, workspace_root=workspace_root
        )
    finally:
        await asyncio.to_thread(shutil.rmtree, scratch_dir, True)


def _merge_rehearsal(
    plan_outcomes: Sequence[EditOutcome],
    planned: Sequence[PlannedEdit],
    rehearsed: Sequence[EditOutcome],
) -> Tuple[List[PlannedEdit], Dict[uuid.UUID, EditOutcome]]:
    """Fold the rehearsal's failures into the plan.

    An edit the rehearsal could not write is reported as ``failed``, with the
    reason docx-editor gave, and is dropped from the plan: the real write is
    only ever asked to do what has already been proven to work, so no comment
    can promise a redline that is not in the margin.
    """
    rehearsed_by_id = {outcome.edit_id: outcome for outcome in rehearsed}
    outcomes: Dict[uuid.UUID, EditOutcome] = {}
    for outcome in plan_outcomes:
        attempt = rehearsed_by_id.get(outcome.edit_id)
        outcomes[outcome.edit_id] = (
            attempt if attempt is not None and attempt.status == "failed" else outcome
        )
    # The plan reports every edit it planned, so each one has an outcome here.
    kept = [edit for edit in planned if outcomes[edit.edit_id].status == "applied"]
    return kept, outcomes


def describe_edit_export(issues: Sequence[Issue]) -> EditExport:
    """Notes for every proposed edit, for an export that writes no redlines.

    The download dialog promises that each edit is described in its issue's
    comment whether or not the tracked-changes option is on, so the notes are
    composed either way; the option only decides whether the fix is also in the
    margin. Nothing is planned and no document is opened here -- there is no
    redline to resolve, rehearse or write -- so every edge case the pre-flight
    reports about placement is moot. A rejected edit is left out, as everywhere
    else.
    """
    outcomes: Dict[uuid.UUID, EditOutcome] = {
        candidate.edit.id: EditOutcome(edit_id=candidate.edit.id, status="skipped")
        for candidate in _candidates(issues)
        if candidate.edit.status != IssueEditStatus.REJECTED
    }
    if not outcomes:
        return EditExport()
    return EditExport(outcomes=outcomes, notes_by_issue=_notes(issues, [], outcomes))


async def plan_edit_export(
    issues: Sequence[Issue],
    markdown: str,
    docx_path: str,
    paragraph_line_ranges: Dict[int, tuple[int, int]],
    workspace_root: Optional[str] = None,
) -> EditExport:
    """Resolve the issues' proposed edits against the original document.

    Leaves `docx_path` untouched: it decides what each edit's fate is and what
    the comments will say about it, so the comment pass can run before anything
    is written into the export. Deciding includes rehearsing the write on a
    scratch copy, so an edit the library refuses is never described as applied.
    """
    candidates = _candidates(issues)
    if not candidates:
        return EditExport()

    lines = document_lines(markdown)
    decisions = resolve_edit_conflicts(candidates, lines)

    if not paragraph_line_ranges:
        outcomes = {o.edit_id: o for o in _unplaceable_outcomes(decisions)}
        return EditExport(
            outcomes=outcomes, notes_by_issue=_notes(issues, decisions, outcomes)
        )

    candidates_by_id: Dict[uuid.UUID, EditCandidate] = {
        candidate.edit.id: candidate for candidate in candidates
    }
    plan = await plan_tracked_changes(
        docx_path,
        decisions,
        candidates_by_id,
        paragraph_line_ranges,
        lines,
        workspace_root=workspace_root,
    )
    rehearsed = await _rehearse(docx_path, plan.planned, workspace_root)
    planned, outcomes = _merge_rehearsal(plan.outcomes, plan.planned, rehearsed)
    return EditExport(
        planned=planned,
        outcomes=outcomes,
        notes_by_issue=_notes(issues, decisions, outcomes),
    )


async def apply_edit_export(
    output_path: str,
    export: EditExport,
    project_id: str,
    workspace_root: Optional[str] = None,
) -> None:
    """Write the planned redlines into the exported file and log the tally.

    Every edit handed over here applied cleanly during the plan's rehearsal, so
    a different outcome now means the rehearsal stopped predicting the real run
    and the comments may be overstating what is in the margin. It is logged
    rather than raised: the file is still worth delivering.
    """
    applied = await apply_tracked_changes(
        output_path, export.planned, workspace_root=workspace_root
    )
    for outcome in applied:
        expected = export.outcomes.get(outcome.edit_id)
        if expected is not None and expected.status != outcome.status:
            logger.warning(
                "DOCX export for project %s wrote edit %s as %s, but its "
                "rehearsal said %s: %s",
                project_id,
                outcome.edit_id,
                outcome.status,
                expected.status,
                outcome.detail,
            )
    merged: Dict[uuid.UUID, EditOutcome] = {
        **export.outcomes,
        **{outcome.edit_id: outcome for outcome in applied},
    }
    if not merged:
        return
    counts = Counter(outcome.status for outcome in merged.values())
    logger.info(
        "DOCX export for project %s handled %d proposed edits: %d applied as "
        "tracked changes, %d in conflict, %d unlocatable, %d not found, "
        "%d ambiguous, %d unsupported, %d failed",
        project_id,
        len(merged),
        counts["applied"],
        counts["conflict"],
        counts["unlocatable"],
        counts["not_found"],
        counts["ambiguous"],
        counts["unsupported"],
        counts["failed"],
    )
