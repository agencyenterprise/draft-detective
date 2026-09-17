"""Writing accepted-or-rejectable redlines into an exported DOCX.

The comment pass tells an author what is wrong; this pass offers the fix as a
Word tracked change (``w:del`` + ``w:ins``), so the author can accept or reject
each proposed edit where they are already reading the document.

Two steps on purpose. `plan_tracked_changes` is a read-only pre-flight against
the *original* file: it resolves every applicable edit to a paragraph, a search
string and an occurrence, and reports the edits it cannot place.
`apply_tracked_changes` then writes the redlines into a file -- the *exported*
one, or, for the caller's rehearsal, a throwaway copy of the original whose
outcomes settle what the comments may claim.

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
    is_table_row,
    locate_in_paragraph,
    source_occurrence,
    unsupported_replacement_reason,
    word_replacement_text,
    word_search_text,
)
from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.services.docx.paragraph_refs import (
    MappedParagraph,
    map_paragraph_refs,
    paragraph_ordinals,
)
from lib.services.edit_conflicts import EditCandidate, EditDecision, pick_winner
from lib.workflows.simple_deep_agent.edit_anchoring import normalize_whitespace

logger = logging.getLogger(__name__)

TRACKED_CHANGE_AUTHOR = "Draft Detective"

# Word cannot show a C0 control character as a reviewable redline, and
# docx-editor refuses one outright. Anything carrying one is reported instead.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# A footnote reference as the markdown carries it, before any syntax is
# stripped: MarkItDown writes a DOCX footnote as a link into the footnotes
# section (`[[1]](#footnote-2)`), and a converter emitting reference-style
# markdown writes `[^1]`. Word carries the reference as a mark, so the
# paragraph's text has no characters for it while the markdown line does.
#
# Matched on the raw line on purpose. A bare `[1]` is left alone: in prose it
# is a visible citation the Word paragraph carries too, and dropping it would
# make a line and its own paragraph look like different passages.
_FOOTNOTE_REFERENCE = re.compile(r"\[\[\d+\]\]\(#footnote-[^)]*\)|\[\^\d+\]")

# How much of a line and a paragraph must agree for them to be the same
# passage. Long enough that no table row can share it with prose.
_MIN_SHARED_PREFIX = 20

# Why nothing could be placed: python-docx and docx-editor disagreed on the
# document's paragraphs, so not one ref could be trusted.
_UNMAPPABLE_DOCUMENT = (
    "the document's paragraphs could not be matched to the file being exported"
)

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
    detail: Optional[str] = None
    winner_id: Optional[uuid.UUID] = None


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
    leaves out entirely. An edit the pre-flight can place is reported as
    ``applied`` here; whether it survives the write is settled by the caller's
    rehearsal (see `lib.services.docx.edit_export`) before any comment claims
    it was applied.
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
) -> Optional[Dict[int, MappedParagraph]]:
    """``{python-docx paragraph index: docx-editor paragraph}`` for a file.

    ``None`` when the two libraries do not agree on the document's paragraphs;
    see `map_paragraph_refs`. Nothing may be redlined in that case.
    """
    with _workspace(workspace_root) as workspace:
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


def _source_line(edit: IssueEdit, document_lines: Sequence[str]) -> Optional[str]:
    """The markdown line the edit was anchored to, if the document still has it."""
    if edit.start_line < 1 or edit.start_line > len(document_lines):
        return None
    return document_lines[edit.start_line - 1]


def _without_footnote_references(line: str) -> str:
    """The markdown line with its footnote reference markers dropped.

    Word shows a footnote as a reference mark rather than as text, so the
    markers are the one thing a markdown line carries that its own paragraph
    never will. Everything else the line says is compared as written.
    """
    return _FOOTNOTE_REFERENCE.sub("", line)


def _shared_prefix_length(left: str, right: str) -> int:
    """How many leading characters two strings agree on."""
    length = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        length += 1
    return length


def _line_belongs_to_paragraph(line: Optional[str], paragraph_text: str) -> bool:
    """Whether the edit's own markdown line is part of the mapped paragraph.

    A paragraph's line range runs to the line before the next body paragraph
    starts, so a table's markdown rows fall inside the range of the paragraph
    above them. Mapping by range alone would hand a table-cell edit to that
    paragraph, and a quote the paragraph happens to carry as well would then be
    redlined on the wrong words. Comparing the whole line against the
    paragraph's text settles it, in three steps:

    1. The line loses its footnote reference markers, which Word carries as
       marks rather than as text, and both are then stripped of markdown. A
       bare `[1]` survives: a bracketed number in prose is a citation the
       paragraph shows as well.
    2. Either text containing the other is the same passage. Both directions
       count: a Word paragraph holding hard line breaks converts to several
       markdown lines, so the line can be the shorter of the two.
    3. Otherwise a shared opening of `_MIN_SHARED_PREFIX` characters is taken
       as the same passage too, which covers drift anywhere in a long
       paragraph -- an inline image, a bookmark, a field result. A prefix that
       long also means both texts are at least that long, and it is more than
       a table row (``| Metric | Value |``) can share with prose.

    Nothing else is the mapped paragraph's own line.
    """
    if line is None:
        return False
    line_text = word_search_text(_without_footnote_references(line))
    para_text = normalize_whitespace(paragraph_text)
    if not line_text or not para_text:
        return False
    if line_text in para_text or para_text in line_text:
        return True
    return _shared_prefix_length(line_text, para_text) >= _MIN_SHARED_PREFIX


def _starts_its_line(line: Optional[str], original_text: str) -> bool:
    """Whether the quote opens its own markdown line.

    Decides how the quote is stripped: ``2019.`` is a list marker at the head
    of a line and a year anywhere else in it.
    """
    if line is None:
        return True
    without_marks = normalize_whitespace(_without_footnote_references(line))
    return without_marks.startswith(normalize_whitespace(original_text))


def _resolve_span(
    edit: IssueEdit,
    paragraph_text: str,
    paragraph_range: Tuple[int, int],
    document_lines: Sequence[str],
    at_line_start: bool,
) -> Tuple[Optional[Tuple[int, int]], EditOutcomeStatus]:
    """Locate the edit's quote in the Word paragraph.

    The quote is markdown; the paragraph is what Word shows, so the syntax is
    stripped first. A quote the paragraph carries more than once is settled
    from the markdown source -- stripping `**Figure 3**` can turn a quote that
    was unique in the source into the second of two identical spans.
    """
    needle = word_search_text(edit.original_text, at_line_start=at_line_start)
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
        at_line_start=at_line_start,
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
    line = _source_line(edit, document_lines)
    # Before any comparison with the paragraph: a row repeating the prose above
    # it word for word would pass the containment test below, and its redline
    # would land on the paragraph instead of the cell.
    if line is not None and is_table_row(line):
        return None, EditOutcome(
            edit_id=edit.id,
            status="unlocatable",
            detail="the edit sits in a table, which the export cannot redline",
        )
    if not _line_belongs_to_paragraph(line, paragraph.text):
        return None, EditOutcome(
            edit_id=edit.id,
            status="unlocatable",
            detail=(
                "the edit's line is not part of the mapped paragraph "
                "(a table or nested block)"
            ),
        )

    at_line_start = _starts_its_line(line, edit.original_text)
    span, status = _resolve_span(
        edit, paragraph.text, paragraph_range, document_lines, at_line_start
    )
    if span is None:
        return None, EditOutcome(edit_id=edit.id, status=status)

    find = paragraph.text[span[0] : span[1]]
    replace_with = word_replacement_text(
        edit.replacement_text, at_line_start=at_line_start
    )
    if replace_with is None:
        return None, EditOutcome(
            edit_id=edit.id,
            status="unsupported",
            detail=unsupported_replacement_reason(edit.replacement_text),
        )
    if replace_with == find:
        return None, EditOutcome(
            edit_id=edit.id,
            status="unsupported",
            detail="the replacement matches the current text once formatting is removed",
        )
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
        one, outcome = _plan_edit(
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
    outcomes: List[EditOutcome] = []
    for edit, result in zip(ordered, results):
        # No revision group means docx-editor wrote nothing -- the operation
        # was a no-op, or it spliced into text an earlier one inserted. Either
        # way there is no redline for the author to accept, so the edit did not
        # apply however quietly the call returned.
        if result.group_id is None:
            logger.warning(
                "Tracked change for edit %s in paragraph %s created no revision "
                "group -- it may have spliced into an earlier insertion",
                edit.edit_id,
                ref,
            )
            outcomes.append(
                EditOutcome(
                    edit_id=edit.edit_id,
                    status="failed",
                    detail="the change produced no tracked revision in Word",
                )
            )
            continue
        outcomes.append(EditOutcome(edit_id=edit.edit_id, status="applied"))
    return outcomes


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
