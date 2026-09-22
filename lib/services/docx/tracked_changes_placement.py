"""Where in a Word paragraph one proposed edit's redline goes, if anywhere.

An edit is anchored to a markdown line; the export has to turn that into
characters of a Word paragraph. Three questions, in order: is the edit's line
part of the mapped paragraph at all (`tracked_changes_lines` answers that one),
which of the paragraph's spans does the quote mean, and can the replacement be
written as a tracked insertion.

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
    rendered_line,
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


def _line_span_in_paragraph(
    edit: IssueEdit,
    paragraph_text: str,
    paragraph_range: Tuple[int, int],
    document_lines: Sequence[str],
) -> Optional[Tuple[int, int]]:
    """Where the edit's own markdown line sits inside the Word paragraph.

    The range's lines are laid against the paragraph in document order, each
    one searched from where the previous one ended. Walking them in order is
    what keeps the boundaries straight, and matching a line on its own is not
    enough for either reason a paragraph can carry it twice:

    - two lines that read exactly alike (``Rose 14%.`` twice), where only
      position tells them apart;
    - a line that an earlier line *contains* -- ``Group A: 14% increase.``
      ends with the whole of ``14% increase.`` -- where the first match of the
      later line sits inside the earlier one, and counting identical lines
      ahead never sees it because the two are not identical.

    ``None`` when the line cannot be found past the lines ahead of it:
    conversion drift, or a line the range covers that the paragraph never
    carried at all -- the line-range mapper runs a paragraph's range up to the
    line before the next one starts, so a nested block's line falls inside it.
    A line that cannot be placed leaves the cursor where it was, so the drift
    of one line does not cost the rest of the paragraph its boundaries.
    """
    first = max(1, paragraph_range[0])
    last = min(len(document_lines), paragraph_range[1])
    cursor = 0
    for number in range(first, last + 1):
        rendered = rendered_line(document_lines[number - 1])
        span = (
            next(
                (
                    found
                    for found in locate_in_paragraph(paragraph_text, rendered)
                    if found[0] >= cursor
                ),
                None,
            )
            if rendered
            else None
        )
        if number == edit.start_line:
            return span
        if span is not None:
            cursor = span[1]
    return None


def _resolve_span(
    edit: IssueEdit,
    paragraph_text: str,
    paragraph_range: Tuple[int, int],
    document_lines: Sequence[str],
) -> Tuple[Optional[Tuple[int, int]], EditOutcomeStatus]:
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

    A paragraph covering several markdown lines -- one per hard line break --
    is a wider haystack than the index was counted in, so the paragraph's lines
    are walked in order until the edit's own is placed, and the quote is looked
    for within that line's span alone. Counting the quote line by line and adding up what sits
    ahead is not enough, and that is the whole reason for going through the
    line: Word keeps nothing where a break was, so joining
    ``First cohort rose 14% `` and ``in 2019; ...`` puts a ``14% in`` in the
    paragraph that neither line carries. Counting per line never sees it, and
    the edit lands on the wrong cohort.

    When the line cannot be located at all the paragraph is the only thing
    left to go on, so a quote it carries exactly once is taken and anything
    repeated is reported rather than guessed at.
    """
    if not edit.display_text:
        return None, "not_found"
    spans = locate_in_paragraph(paragraph_text, edit.display_text)
    if not spans:
        return None, "not_found"

    if paragraph_range[0] < edit.start_line or paragraph_range[1] > edit.start_line:
        line_span = _line_span_in_paragraph(
            edit, paragraph_text, paragraph_range, document_lines
        )
        if line_span is not None:
            within = locate_in_paragraph(
                paragraph_text[line_span[0] : line_span[1]], edit.display_text
            )
            if edit.display_occurrence < len(within):
                start, end = within[edit.display_occurrence]
                return (line_span[0] + start, line_span[0] + end), "applied"
        return (spans[0], "applied") if len(spans) == 1 else (None, "ambiguous")

    if len(spans) == 1:
        return spans[0], "applied"
    if edit.display_occurrence >= len(spans):
        return None, "ambiguous"
    return spans[edit.display_occurrence], "applied"


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

    span, status = _resolve_span(edit, paragraph.text, paragraph_range, document_lines)
    if span is None:
        return None, EditOutcome(edit_id=edit.id, status=status)

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
