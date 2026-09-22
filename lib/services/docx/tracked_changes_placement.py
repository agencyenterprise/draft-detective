"""Where in a Word paragraph one proposed edit's redline goes, if anywhere.

An edit is anchored to a markdown line; the export has to turn that into
characters of a Word paragraph. Three questions, in order: is the edit's line
part of the mapped paragraph at all (`tracked_changes_lines` answers that one),
which of the paragraph's spans does the quote mean, and can the replacement be
written as a tracked insertion.

The middle one is the awkward one, and `_resolve_span` says why: a paragraph
that covers several markdown lines cannot be indexed by an occurrence counted
in one of them, so a quote it repeats is reported instead of placed.

`plan_edit` answers all three for one edit and is the only name
`tracked_changes_planning` needs from here.
"""

import re
from typing import Optional, Sequence, Tuple

from lib.models.issue_edit import IssueEdit
from lib.services.docx.edit_text import (
    LINK_DESTINATION_CHANGED,
    is_table_row,
    unsupported_replacement_reason,
)
from lib.services.docx.paragraph_refs import MappedParagraph
from lib.services.docx.tracked_changes_lines import (
    line_belongs_to_paragraph,
    source_line,
)
from lib.services.docx.tracked_changes_models import (
    EditOutcome,
    EditOutcomeStatus,
    PlannedEdit,
)
from lib.services.markdown_text import link_destinations
from lib.services.text_location import all_offsets, locate_in_paragraph

# Word cannot show a C0 control character as a reviewable redline, and
# docx-editor refuses one outright. Anything carrying one is reported instead.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


# Why a repeat inside a paragraph that covers several markdown lines is left
# alone. `display_occurrence` was counted on the edit's own line, so it does
# not index the paragraph, and every way of rebasing it was wrong in a
# different way (see `_resolve_span`).
REPEATS_ACROSS_LINES = (
    "the quoted text repeats inside a paragraph that spans several lines "
    "of the document"
)


def _resolve_span(
    edit: IssueEdit, paragraph_text: str, paragraph_range: Tuple[int, int]
) -> Tuple[Optional[Tuple[int, int]], EditOutcomeStatus, Optional[str]]:
    """Locate the edit's quote in the Word paragraph.

    `display_text` is the quote as the document renders it, worked out when the
    edit was reported, so nothing has to be stripped here. What is left is
    which of the paragraph's spans the edit meant, and that depends on how much
    of the document the paragraph covers.

    A paragraph that is the edit's line and nothing else answers it directly:
    `display_occurrence` counted the rendered repeats of that line, so it is
    the paragraph's own index. `**Figure 3**` is a unique quote of ``Figure 3
    and **Figure 3**`` and the second of two identical spans once the page has
    it.

    A paragraph covering several markdown lines is a different matter. A hard
    line break inside a Word paragraph converts to one markdown line per
    break, and Word keeps *nothing* where the break was -- no separator to
    rebuild the join from. `display_occurrence` was counted in one line and the
    paragraph is several, so it cannot be used as it stands, and every attempt
    to rebase it onto the paragraph failed somewhere else:

    - adding up the quote's occurrences on the lines ahead misses a match that
      straddles the join, since ``First cohort rose 14% `` and ``in 2019; ...``
      put a ``14% in`` in the paragraph that neither line carries;
    - locating the edit's own line and counting inside it misses the case
      where an earlier line *contains* the later one, so ``Group A: 14%
      increase.`` swallows the whole of ``14% increase.``;
    - walking the lines in document order behind a cursor fixes both and still
      leaves the boundaries to conversion drift, with no way to tell a
      mislocated line from a line the paragraph never carried.

    So a repeat in such a paragraph is reported rather than placed. It costs
    little: paragraphs spanning several markdown lines are about 4.5% of the
    converted DOCX paragraphs, and almost all of them are reference entries
    and author blocks -- passages an edit rarely needs to reach, and where
    guessing wrong would redline the wrong author's name. A quote the
    paragraph carries once is applied as it always was, drift or no drift.
    """
    if not edit.display_text:
        return None, "not_found", None
    spans = locate_in_paragraph(paragraph_text, edit.display_text)
    if not spans:
        return None, "not_found", None

    if paragraph_range[0] < edit.start_line or paragraph_range[1] > edit.start_line:
        if len(spans) == 1:
            return spans[0], "applied", None
        return None, "ambiguous", REPEATS_ACROSS_LINES

    if len(spans) == 1:
        return spans[0], "applied", None
    if edit.display_occurrence >= len(spans):
        return None, "ambiguous", None
    return spans[edit.display_occurrence], "applied", None


def _with_boundary_whitespace(
    span: Tuple[int, int], paragraph_text: str, original_text: str
) -> Tuple[int, int]:
    """Grow the span over the whitespace the quote itself asked for.

    A quote is located by its words: `display_text` normalizes ``" bad "``
    to ``bad``, so the span found covers ``bad`` alone. Writing ``" good "``
    over it would then double the spaces around it, and deleting it would leave
    two spaces behind. The quote said which spaces it owns, so each side it
    opened or closed with whitespace takes the paragraph's own run of
    whitespace there with it.
    """
    start, end = span
    if original_text[:1].isspace():
        while start > 0 and paragraph_text[start - 1].isspace():
            start -= 1
    if original_text[-1:].isspace():
        while end < len(paragraph_text) and paragraph_text[end].isspace():
            end += 1
    return start, end


def plan_edit(
    edit: IssueEdit,
    paragraph_index: int,
    paragraph: MappedParagraph,
    paragraph_range: Tuple[int, int],
    document_lines: Sequence[str],
) -> Tuple[Optional[PlannedEdit], EditOutcome]:
    """Turn one applicable edit into a redline, or say why it cannot be one."""
    line = source_line(edit, document_lines)
    # Before any comparison with the paragraph: a row repeating the prose above
    # it word for word would pass the containment test below, and its redline
    # would land on the paragraph instead of the cell.
    if line is not None and is_table_row(line):
        return None, EditOutcome(
            edit_id=edit.id,
            status="unlocatable",
            detail="the edit sits in a table, which the export cannot redline",
        )
    if not line_belongs_to_paragraph(line, paragraph.text):
        return None, EditOutcome(
            edit_id=edit.id,
            status="unlocatable",
            detail=(
                "the edit's line is not part of the mapped paragraph "
                "(a table or nested block)"
            ),
        )

    span, status, detail = _resolve_span(edit, paragraph.text, paragraph_range)
    if span is None:
        return None, EditOutcome(edit_id=edit.id, status=status, detail=detail)

    span = _with_boundary_whitespace(span, paragraph.text, edit.original_text)
    find = paragraph.text[span[0] : span[1]]
    replace_with = edit.display_replacement
    unsupported = unsupported_replacement_reason(edit.replacement_text)
    if unsupported is not None:
        return None, EditOutcome(
            edit_id=edit.id,
            status="unsupported",
            detail=unsupported,
        )
    if link_destinations(edit.replacement_text) != link_destinations(
        edit.original_text
    ):
        return None, EditOutcome(
            edit_id=edit.id,
            status="unsupported",
            detail=LINK_DESTINATION_CHANGED,
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
