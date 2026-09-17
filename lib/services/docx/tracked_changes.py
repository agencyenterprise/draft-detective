"""Writing accepted-or-rejectable redlines into an exported DOCX.

The comment pass tells an author what is wrong; this pass offers the fix as a
Word tracked change (``w:del`` + ``w:ins``), so the author can accept or reject
each proposed edit where they are already reading the document.

Two steps on purpose. `plan_tracked_changes` is a read-only pre-flight against
the *original* file: it resolves every applicable edit to a paragraph, a search
string and an occurrence, and reports the edits it cannot place. Its outcomes
are what the comments say about each edit, so the comment pass has to run after
it. `apply_tracked_changes` then writes the redlines into the *exported* file.

Ordering is not a preference. python-docx paragraph text stops carrying
inserted and deleted runs once tracked changes exist, so the paragraph index
map the comment pass anchors to is only valid before this pass runs:
comments first, save, then redlines.
"""

import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from typing import Dict, Iterator, List, Literal, Mapping, Optional, Sequence, Tuple

from docx import Document as PythonDocxDocument
from docx_editor import BatchOperationError, Document as EditorDocument, EditOperation
from pydantic import BaseModel

from lib.models.issue_edit import IssueEdit
from lib.services.docx.edit_text import (
    all_offsets,
    locate_in_paragraph,
    source_occurrence,
    word_search_text,
)
from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.services.docx.paragraph_refs import MappedParagraph, map_paragraph_refs
from lib.services.edit_conflicts import EditDecision

logger = logging.getLogger(__name__)

TRACKED_CHANGE_AUTHOR = "Draft Detective"

# Word cannot show a C0 control character as a reviewable redline, and
# docx-editor refuses one outright. Anything carrying one is reported instead.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

EditOutcomeStatus = Literal[
    "applied", "conflict", "unlocatable", "not_found", "ambiguous", "failed"
]


class EditOutcome(BaseModel):
    """What became of one proposed edit in the export."""

    edit_id: uuid.UUID
    status: EditOutcomeStatus
    detail: Optional[str] = None


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
    span: Tuple[int, int]


class TrackedChangesPlan(BaseModel):
    """The redlines to write, plus what to say about every edit considered.

    `outcomes` covers each decision except rejected edits, which the export
    leaves out entirely. An edit that the pre-flight can place is reported as
    ``applied`` before anything is written -- the comment text is composed from
    these outcomes, and a paragraph whose batch later fails is only logged.
    """

    planned: List[PlannedEdit]
    outcomes: List[EditOutcome]


@contextmanager
def _workspace(root: Optional[str]) -> Iterator[str]:
    """A private docx-editor workspace, removed again afterwards.

    One per invocation so that two exports of the same document never contend
    for the same unpacked copy.
    """
    path = tempfile.mkdtemp(prefix="docx-editor-", dir=root)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _paragraph_map(
    docx_path: str, workspace_root: Optional[str]
) -> Dict[int, MappedParagraph]:
    """``{python-docx paragraph index: docx-editor paragraph}`` for a file."""
    with _workspace(workspace_root) as workspace:
        doc = EditorDocument.open(
            docx_path, author=TRACKED_CHANGE_AUTHOR, workspace_dir=workspace
        )
        try:
            editor_paragraphs = doc.list_paragraphs_structured(limit=None)
            in_table = {
                ref
                for ref, location in doc.list_paragraph_locations()
                if location.in_table
            }
        finally:
            doc.close()
    texts = [
        paragraph.text
        for paragraph in PythonDocxDocument(docx_path).paragraphs
        if paragraph.text.strip()
    ]
    return map_paragraph_refs(texts, editor_paragraphs, in_table)


def _resolve_span(
    edit: IssueEdit,
    paragraph_text: str,
    paragraph_range: Tuple[int, int],
    document_lines: Sequence[str],
) -> Tuple[Optional[Tuple[int, int]], EditOutcomeStatus]:
    """Locate the edit's quote in the Word paragraph.

    The quote is markdown; the paragraph is what Word shows, so the syntax is
    stripped first. A quote the paragraph carries more than once is settled
    from the markdown source -- stripping `**Figure 3**` can turn a quote that
    was unique in the source into the second of two identical spans.
    """
    needle = word_search_text(edit.original_text)
    if not needle:
        return None, "not_found"
    spans = locate_in_paragraph(paragraph_text, needle)
    if not spans:
        return None, "not_found"
    if len(spans) == 1:
        return spans[0], "applied"
    occurrence = source_occurrence(
        document_lines,
        paragraph_range[0],
        paragraph_range[1],
        edit.start_line,
        edit.original_text,
    )
    if occurrence is None or occurrence >= len(spans):
        return None, "ambiguous"
    return spans[occurrence], "applied"


def _plan_edit(
    edit: IssueEdit,
    paragraph_index: int,
    paragraph: MappedParagraph,
    paragraph_range: Tuple[int, int],
    document_lines: Sequence[str],
) -> Tuple[Optional[PlannedEdit], EditOutcome]:
    """Turn one applicable edit into a redline, or say why it cannot be one."""
    span, status = _resolve_span(edit, paragraph.text, paragraph_range, document_lines)
    if span is None:
        return None, EditOutcome(edit_id=edit.id, status=status)

    find = paragraph.text[span[0] : span[1]]
    replace_with = word_search_text(edit.replacement_text)
    if _CONTROL_CHARS.search(find) or _CONTROL_CHARS.search(replace_with):
        return None, EditOutcome(
            edit_id=edit.id,
            status="failed",
            detail="quoted or replacement text carries a control character",
        )

    # docx-editor counts occurrences of the exact search string in the
    # paragraph's visible text, which is not the whitespace-normalized count
    # the span came from, so the index is recounted on `find` itself.
    occurrence = len(
        [offset for offset in all_offsets(paragraph.text, find) if offset < span[0]]
    )
    planned = PlannedEdit(
        edit_id=edit.id,
        paragraph_ref=paragraph.ref,
        paragraph_index=paragraph_index,
        find=find,
        replace_with=replace_with,
        occurrence=occurrence,
        span=span,
    )
    return planned, EditOutcome(edit_id=edit.id, status="applied")


def _overlapping(planned: Sequence[PlannedEdit], candidate: PlannedEdit) -> bool:
    """Whether a paragraph already carries a redline over the same characters.

    Conflicts were resolved per markdown line, but one Word paragraph can cover
    several lines (a list, a table row), so two edits from different lines can
    still land on the same words. They must not both reach docx-editor: an
    operation whose search text overlaps text an earlier operation inserted
    corrupts the paragraph silently.
    """
    return any(
        other.paragraph_ref == candidate.paragraph_ref
        and other.span[0] < candidate.span[1]
        and candidate.span[0] < other.span[1]
        for other in planned
    )


def _plan_sync(
    docx_path: str,
    decisions: Sequence[EditDecision],
    edits_by_id: Mapping[uuid.UUID, IssueEdit],
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
    planned: List[PlannedEdit] = []
    for decision in applicable:
        edit = edits_by_id[decision.edit_id]
        paragraph_index = find_paragraph_by_line_range(
            paragraph_line_ranges, edit.start_line, edit.start_line
        )
        paragraph = (
            paragraphs.get(paragraph_index) if paragraph_index is not None else None
        )
        if paragraph_index is None or paragraph is None:
            outcomes.append(EditOutcome(edit_id=edit.id, status="not_found"))
            continue
        one, outcome = _plan_edit(
            edit,
            paragraph_index,
            paragraph,
            paragraph_line_ranges[paragraph_index],
            document_lines,
        )
        if one is not None and _overlapping(planned, one):
            outcome = EditOutcome(
                edit_id=edit.id,
                status="conflict",
                detail="overlaps another proposed edit in the same paragraph",
            )
            one = None
        if one is not None:
            planned.append(one)
        outcomes.append(outcome)
    return TrackedChangesPlan(planned=planned, outcomes=outcomes)


async def plan_tracked_changes(
    docx_path: str,
    decisions: Sequence[EditDecision],
    edits_by_id: Mapping[uuid.UUID, IssueEdit],
    paragraph_line_ranges: Dict[int, Tuple[int, int]],
    document_lines: Sequence[str],
    workspace_root: Optional[str] = None,
) -> TrackedChangesPlan:
    """Resolve the applicable edits against `docx_path` without changing it.

    Runs against the original document so the comments can describe each edit's
    fate accurately. `document_lines` is the main document's markdown, split
    the way the edits were anchored.
    """
    return await asyncio.to_thread(
        _plan_sync,
        docx_path,
        decisions,
        edits_by_id,
        paragraph_line_ranges,
        document_lines,
        workspace_root,
    )


def _apply_paragraph(
    doc: EditorDocument, ref: str, edits: List[PlannedEdit]
) -> List[EditOutcome]:
    """Write one paragraph's redlines in a single atomic batch.

    Back-to-front: docx-editor matches each operation against the paragraph as
    it stands, so doing the later spans first leaves the earlier ones' offsets
    and occurrence counts untouched.
    """
    ordered = sorted(edits, key=lambda edit: edit.span, reverse=True)
    try:
        results = doc.batch_edit(
            [
                EditOperation.replace(
                    edit.find,
                    edit.replace_with,
                    paragraph=ref,
                    occurrence=edit.occurrence,
                )
                for edit in ordered
            ]
        )
    # ValueError as well as BatchOperationError: docx-editor validates an
    # operation's own arguments when it is built, and one paragraph's rejection
    # must not cost the rest of the document its redlines.
    except (BatchOperationError, ValueError) as error:
        reason = error.reason if isinstance(error, BatchOperationError) else str(error)
        logger.warning(
            "Tracked changes for paragraph %s were rejected: %s", ref, reason
        )
        return [
            EditOutcome(edit_id=edit.edit_id, status="failed", detail=reason)
            for edit in ordered
        ]
    for edit, result in zip(ordered, results):
        if result.group_id is None:
            logger.warning(
                "Tracked change for edit %s in paragraph %s created no revision "
                "group -- it may have spliced into an earlier insertion",
                edit.edit_id,
                ref,
            )
    return [EditOutcome(edit_id=edit.edit_id, status="applied") for edit in ordered]


def _apply_sync(
    docx_path: str,
    planned: Sequence[PlannedEdit],
    author: str,
    workspace_root: Optional[str],
) -> List[EditOutcome]:
    by_paragraph: Dict[str, List[PlannedEdit]] = {}
    for edit in planned:
        by_paragraph.setdefault(edit.paragraph_ref, []).append(edit)

    outcomes: List[EditOutcome] = []
    with _workspace(workspace_root) as workspace:
        doc = EditorDocument.open(docx_path, author=author, workspace_dir=workspace)
        try:
            for ref in sorted(by_paragraph):
                outcomes.extend(_apply_paragraph(doc, ref, by_paragraph[ref]))
            doc.save()
        finally:
            doc.close()
    return outcomes


async def apply_tracked_changes(
    docx_path: str,
    planned: Sequence[PlannedEdit],
    author: str = TRACKED_CHANGE_AUTHOR,
    workspace_root: Optional[str] = None,
) -> List[EditOutcome]:
    """Write the planned redlines into `docx_path`, in place.

    The refs a plan carries were computed on the original file and stay valid
    here: they are anchored to a hash of the paragraph's visible text, which
    adding Word comments does not change. A paragraph whose batch is rejected
    leaves the rest of the document redlined -- each paragraph is its own
    batch, and its edits come back as ``failed``.
    """
    if not planned:
        return []
    return await asyncio.to_thread(
        _apply_sync, docx_path, planned, author, workspace_root
    )
