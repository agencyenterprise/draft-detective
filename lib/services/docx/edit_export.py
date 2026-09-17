"""The proposed-edit half of a DOCX export, from issue rows to redlines.

Sits between `generate_docx` and the two passes it drives: conflict resolution
over the issues' proposed edits, the read-only pre-flight that resolves each
survivor to a paragraph, the comment notes composed from those outcomes, and
the apply step that writes the redlines into the finished file.
"""

import logging
import uuid
from collections import Counter
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from lib.models.issue import Issue
from lib.models.issue_edit import IssueEdit
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
    """Comment blocks per issue, naming the workflow a conflict lost to."""
    issue_of_edit: Dict[uuid.UUID, Issue] = {
        row.id: issue for issue in issues for row in issue.edit_rows
    }
    winner_names: Dict[uuid.UUID, str] = {}
    for decision in decisions:
        winner = issue_of_edit.get(decision.winner_id) if decision.winner_id else None
        if winner is not None:
            winner_names[decision.edit_id] = _workflow_name(winner)
    return {
        issue.id: notes
        for issue in issues
        if (notes := build_edit_notes(issue.edit_rows, outcomes, winner_names))
    }


async def plan_edit_export(
    issues: Sequence[Issue],
    markdown: str,
    docx_path: str,
    paragraph_line_ranges: Dict[int, tuple[int, int]],
    workspace_root: Optional[str] = None,
) -> EditExport:
    """Resolve the issues' proposed edits against the original document.

    Read-only: it decides what each edit's fate is and what the comments will
    say about it, so the comment pass can run before anything is written.
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

    edits_by_id: Dict[uuid.UUID, IssueEdit] = {c.edit.id: c.edit for c in candidates}
    plan = await plan_tracked_changes(
        docx_path,
        decisions,
        edits_by_id,
        paragraph_line_ranges,
        lines,
        workspace_root=workspace_root,
    )
    outcomes = {outcome.edit_id: outcome for outcome in plan.outcomes}
    return EditExport(
        planned=plan.planned,
        outcomes=outcomes,
        notes_by_issue=_notes(issues, decisions, outcomes),
    )


async def apply_edit_export(
    output_path: str,
    export: EditExport,
    project_id: str,
    workspace_root: Optional[str] = None,
) -> None:
    """Write the planned redlines into the exported file and log the tally."""
    applied = await apply_tracked_changes(
        output_path, export.planned, workspace_root=workspace_root
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
        "%d ambiguous, %d failed",
        project_id,
        len(merged),
        counts["applied"],
        counts["conflict"],
        counts["unlocatable"],
        counts["not_found"],
        counts["ambiguous"],
        counts["failed"],
    )
