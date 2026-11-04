"""The proposed-edit half of a DOCX export, from issue rows to redlines.

Sits between `generate_docx` and the passes it drives: conflict resolution over
the issues' proposed edits, the read-only pre-flight that resolves each
survivor to a paragraph, the comment notes composed from those outcomes, and
the write that puts the redlines into the finished file.

Comments have to be written before the redlines -- python-docx stops reading
inserted and deleted runs as paragraph text, so the paragraph map the comment
pass anchors to is only valid beforehand -- and until the write has actually
been attempted, nothing knows whether docx-editor will take a given operation.
So the comments are written on the pre-flight's word and the redlines after
them, and if docx-editor refused any redline the file is written again from the
original, with those edits noted as failed and left out. No comment in the
delivered file claims a redline the margin does not have, and the usual export,
where docx-editor takes everything, writes its redlines once.

`describe_edit_export` is the comments-only counterpart: an export that writes
no redlines still describes every edit in its issue's comment, and does so
without opening the document at all.
"""

import asyncio
import logging
import os
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence

from pydantic import BaseModel, Field

from lib.models.issue import Issue
from lib.models.issue_edit import IssueEditStatus
from lib.services.docx.edit_conflicts import (
    EditCandidate,
    EditDecision,
    resolve_edit_conflicts,
)
from lib.services.docx.edit_notes import EditNote, build_edit_notes
from lib.services.docx.tracked_changes import (
    EditOutcome,
    PlannedEdit,
    apply_tracked_changes,
    plan_tracked_changes,
    unplaceable_outcomes,
)
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.simple_deep_agent.edit_anchoring import document_lines

logger = logging.getLogger(__name__)


class EditExport(BaseModel):
    """Everything the export still has to do about proposed edits."""

    planned: list[PlannedEdit] = Field(default_factory=list)
    outcomes: dict[uuid.UUID, EditOutcome] = Field(default_factory=dict)
    notes_by_issue: dict[uuid.UUID, list[EditNote]] = Field(default_factory=dict)
    # The workflow each conflict lost to, by losing edit, kept so the notes can
    # be composed again once the write has settled which edits failed.
    winner_names: dict[uuid.UUID, str] = Field(default_factory=dict)

    def notes_for(self, issue_id: uuid.UUID) -> list[EditNote]:
        return self.notes_by_issue.get(issue_id, [])


def _workflow_name(issue: Issue) -> str:
    manifest = get_workflow_manifest(issue.workflow_type, raise_exception=False)
    return manifest.name if manifest else str(issue.workflow_type)


def _candidates(issues: Sequence[Issue]) -> list[EditCandidate]:
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


def _winner_names(
    issues: Sequence[Issue],
    decisions: Sequence[EditDecision],
    outcomes: dict[uuid.UUID, EditOutcome],
) -> dict[uuid.UUID, str]:
    """The workflow each conflict lost to, by losing edit.

    A conflict is decided either per markdown line, before the document is
    opened, or per Word paragraph by the pre-flight; the winner's id comes off
    the decision in the first case and off the outcome in the second, and both
    resolve to a workflow name the same way.
    """
    issue_of_edit: dict[uuid.UUID, Issue] = {
        row.id: issue for issue in issues for row in issue.edit_rows
    }
    winner_ids: dict[uuid.UUID, uuid.UUID] = {
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
    winner_names: dict[uuid.UUID, str] = {}
    for edit_id, winner_id in winner_ids.items():
        winner = issue_of_edit.get(winner_id)
        if winner is not None:
            winner_names[edit_id] = _workflow_name(winner)
    return winner_names


def _export(
    issues: Sequence[Issue],
    planned: list[PlannedEdit],
    outcomes: dict[uuid.UUID, EditOutcome],
    winner_names: dict[uuid.UUID, str],
) -> EditExport:
    """The export, with a comment block per issue composed from `outcomes`."""
    return EditExport(
        planned=planned,
        outcomes=outcomes,
        notes_by_issue={
            issue.id: notes
            for issue in issues
            if (notes := build_edit_notes(issue.edit_rows, outcomes, winner_names))
        },
        winner_names=winner_names,
    )


def _with_failures(
    issues: Sequence[Issue], export: EditExport, failures: Sequence[EditOutcome]
) -> EditExport:
    """The export once the write has refused `failures`.

    Each is reported as ``failed``, with the reason docx-editor gave, and is
    dropped from the plan: the next write is only asked to do what has already
    been shown to work, so no comment can promise a redline that is not in the
    margin.
    """
    failed = {outcome.edit_id: outcome for outcome in failures}
    return _export(
        issues,
        [edit for edit in export.planned if edit.edit_id not in failed],
        {**export.outcomes, **failed},
        export.winner_names,
    )


def describe_edit_export(issues: Sequence[Issue]) -> EditExport:
    """Notes for every proposed edit, for an export that writes no redlines.

    The download dialog promises that each edit is described in its issue's
    comment whether or not the tracked-changes option is on, so the notes are
    composed either way; the option only decides whether the fix is also in the
    margin. Nothing is planned and no document is opened here -- there is no
    redline to resolve or write -- so every edge case the pre-flight reports
    about placement is moot. A rejected edit is left out, as everywhere else.
    """
    outcomes: dict[uuid.UUID, EditOutcome] = {
        candidate.edit.id: EditOutcome(edit_id=candidate.edit.id, status="skipped")
        for candidate in _candidates(issues)
        if candidate.edit.status != IssueEditStatus.REJECTED
    }
    if not outcomes:
        return EditExport()
    return _export(issues, [], outcomes, _winner_names(issues, [], outcomes))


async def plan_edit_export(
    issues: Sequence[Issue],
    markdown: str,
    docx_path: str,
    paragraph_line_ranges: dict[int, tuple[int, int]],
    workspace_root: str | None = None,
) -> EditExport:
    """Resolve the issues' proposed edits against the original document.

    Leaves `docx_path` untouched: it decides what each edit's fate is and what
    the comments will say about it, so the comment pass can run before anything
    is written into the export. An edit the pre-flight can place is noted as
    applied; `write_edit_export` corrects that if docx-editor turns it down.
    """
    candidates = _candidates(issues)
    if not candidates:
        return EditExport()

    lines = document_lines(markdown)
    decisions = resolve_edit_conflicts(candidates, lines)

    if not paragraph_line_ranges:
        # The line-range mapper returns an empty map when the document converts
        # differently than it did at ingestion, so nothing can be anchored.
        outcomes = {o.edit_id: o for o in unplaceable_outcomes(decisions)}
        return _export(issues, [], outcomes, _winner_names(issues, decisions, outcomes))

    candidates_by_id: dict[uuid.UUID, EditCandidate] = {
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
    outcomes = {outcome.edit_id: outcome for outcome in plan.outcomes}
    return _export(
        issues, plan.planned, outcomes, _winner_names(issues, decisions, outcomes)
    )


async def write_edit_export(
    issues: Sequence[Issue],
    export: EditExport,
    write_comments: Callable[[EditExport], Awaitable[str]],
    project_id: str,
    workspace_root: str | None = None,
) -> str:
    """Write the commented export with its redlines, and return its path.

    `write_comments` writes a fresh commented copy of the original from an
    export's notes and returns where it put it; the redlines go into that copy.
    If docx-editor refused any of them, the copy's comments promise redlines it
    does not have, so it is deleted and the file written again with those edits
    noted as failed and left out.

    docx-editor is deterministic: the same operations against the same
    paragraphs of the same document produce the same result, and the plan's
    refs are anchored to a hash of each paragraph's visible text, which the
    comment pass does not change. So the second write takes everything the
    first one did. If that ever stops holding it is logged rather than raised:
    the file is still worth delivering.
    """
    output_path = await write_comments(export)
    written = await apply_tracked_changes(
        output_path, export.planned, workspace_root=workspace_root
    )
    failures = [outcome for outcome in written if outcome.status != "applied"]
    if failures:
        logger.info(
            "DOCX export for project %s is written again: docx-editor refused "
            "%d of its %d tracked changes",
            project_id,
            len(failures),
            len(written),
        )
        await asyncio.to_thread(os.remove, output_path)
        export = _with_failures(issues, export, failures)
        output_path = await write_comments(export)
        written = await apply_tracked_changes(
            output_path, export.planned, workspace_root=workspace_root
        )
        _log_second_write_failures(project_id, written)
    _log_tally(project_id, {**export.outcomes, **{o.edit_id: o for o in written}})
    return output_path


def _log_second_write_failures(project_id: str, written: Sequence[EditOutcome]) -> None:
    """Warn about each edit the second write refused after the first took it.

    Its comment says it was applied, so the comments now overstate what is in
    the margin.
    """
    for outcome in written:
        if outcome.status != "applied":
            logger.warning(
                "DOCX export for project %s wrote edit %s as %s on its second "
                "write, though the first applied it: %s",
                project_id,
                outcome.edit_id,
                outcome.status,
                outcome.detail,
            )


def _log_tally(project_id: str, outcomes: dict[uuid.UUID, EditOutcome]) -> None:
    if not outcomes:
        return
    counts = Counter(outcome.status for outcome in outcomes.values())
    logger.info(
        "DOCX export for project %s handled %d proposed edits: %d applied as "
        "tracked changes, %d in conflict, %d unlocatable, %d not found, "
        "%d ambiguous, %d unsupported, %d failed",
        project_id,
        len(outcomes),
        counts["applied"],
        counts["conflict"],
        counts["unlocatable"],
        counts["not_found"],
        counts["ambiguous"],
        counts["unsupported"],
        counts["failed"],
    )
