"""Where in a Word paragraph one proposed edit's redline goes, if anywhere.

An edit is anchored to a markdown line; the export has to turn that into
characters of a Word paragraph. Three questions, in order: is the edit's line
part of the mapped paragraph at all (`lines` answers that one),
which of the paragraph's spans does the quote mean, and can the replacement be
written as a tracked insertion.

The middle one is the awkward one, and `quote_span.resolve_quote_span` says why: a paragraph
that covers several markdown lines cannot be indexed by an occurrence counted
in one of them, so a quote it repeats is reported instead of placed.

`plan_edit` answers all three for one edit and is the only name
`planning` needs from here. A quote that crosses footnote references is placed
by `footnotes` instead, as one redline per stretch it changes.
"""

import re
from collections.abc import Sequence

from lib.models.issue_edit import IssueEdit
from lib.services.docx.edit_text import (
    LINK_DESTINATION_CHANGED,
    UNCHANGED_ONCE_RENDERED,
    unsupported_replacement_reason,
)
from lib.services.docx.paragraph_refs import MappedParagraph
from lib.services.docx.tracked_changes.footnotes import (
    carries_footnotes,
    place_around_footnotes,
)
from lib.services.docx.tracked_changes.lines import membership_outcome
from lib.services.docx.tracked_changes.models import (
    EditOutcome,
    PlannedEdit,
)
from lib.services.docx.tracked_changes.quote_span import resolve_quote_span
from lib.services.text.location import all_offsets
from lib.services.text.markdown_rendering import link_destinations

# Word cannot show a C0 control character as a reviewable redline, and
# docx-editor refuses one outright. Anything carrying one is reported instead.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _with_boundary_whitespace(
    span: tuple[int, int], paragraph_text: str, original_text: str
) -> tuple[int, int]:
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


# One redline as `_locate` hands it over: the paragraph span and its new text.
_Piece = tuple[tuple[int, int], str]


def _locate(
    edit: IssueEdit,
    paragraph_text: str,
    paragraph_range: tuple[int, int],
    document_lines: Sequence[str],
) -> list[_Piece] | EditOutcome:
    """The spans to redline and what to write over each, or why there are none.

    A quote is matched as the document renders it, and is one redline. A quote
    carrying footnote references is matched around them instead, as one
    redline per stretch between references that the edit changes (see
    `footnotes`). Never as rendered: Word keeps a reference as a mark with no
    text, so a paragraph showing the rendered ``Claim[1]`` can only be showing a
    literal citation, never the passage the quote means.
    """
    if carries_footnotes(edit):
        placed = place_around_footnotes(edit, paragraph_text)
        if placed.pieces:
            return [(piece.span, piece.replace_with) for piece in placed.pieces]
        if placed.detail is not None:
            return EditOutcome(
                edit_id=edit.id, status="unsupported", detail=placed.detail
            )
        return EditOutcome(edit_id=edit.id, status="not_found")
    span, status, detail = resolve_quote_span(
        edit, paragraph_text, paragraph_range, document_lines
    )
    if span is None:
        return EditOutcome(edit_id=edit.id, status=status, detail=detail)
    span = _with_boundary_whitespace(span, paragraph_text, edit.original_text)
    return [(span, edit.display_replacement)]


def _refusal(
    edit: IssueEdit, paragraph_text: str, pieces: list[_Piece]
) -> EditOutcome | None:
    """Why located redlines still cannot be written, or None when they can."""
    unsupported = unsupported_replacement_reason(edit.replacement_text)
    if unsupported is not None:
        return EditOutcome(edit_id=edit.id, status="unsupported", detail=unsupported)
    if link_destinations(edit.replacement_text) != link_destinations(
        edit.original_text
    ):
        return EditOutcome(
            edit_id=edit.id, status="unsupported", detail=LINK_DESTINATION_CHANGED
        )
    finds = [paragraph_text[start:end] for (start, end), _ in pieces]
    if all(find == replace for find, (_, replace) in zip(finds, pieces)):
        return EditOutcome(
            edit_id=edit.id, status="unsupported", detail=UNCHANGED_ONCE_RENDERED
        )
    if any(
        _CONTROL_CHARS.search(find) or _CONTROL_CHARS.search(replace)
        for find, (_, replace) in zip(finds, pieces)
    ):
        return EditOutcome(
            edit_id=edit.id,
            status="failed",
            detail="quoted or replacement text carries a control character",
        )
    return None


def _planned(
    edit: IssueEdit,
    paragraph_index: int,
    paragraph: MappedParagraph,
    piece: _Piece,
) -> PlannedEdit:
    span, replace_with = piece
    find = paragraph.text[span[0] : span[1]]
    # docx-editor counts occurrences of the exact search string in the
    # paragraph's visible text, which is not the whitespace-normalized count
    # the span came from, so the index is recounted on `find` itself.
    occurrence = len(
        [offset for offset in all_offsets(paragraph.text, find) if offset < span[0]]
    )
    return PlannedEdit(
        edit_id=edit.id,
        paragraph_ref=paragraph.ref,
        paragraph_index=paragraph_index,
        find=find,
        replace_with=replace_with,
        occurrence=occurrence,
        span=span,
    )


def plan_edit(
    edit: IssueEdit,
    paragraph_index: int,
    paragraph: MappedParagraph,
    paragraph_range: tuple[int, int],
    document_lines: Sequence[str],
) -> tuple[list[PlannedEdit], EditOutcome]:
    """Turn one applicable edit into its redlines, or say why it has none.

    Usually one redline. A quote that crosses footnote references gets one per
    stretch it changes between them, all under the edit's id: they are written,
    refused and reported together.
    """
    refused = membership_outcome(edit, paragraph.text, document_lines)
    if refused is not None:
        return [], refused
    located = _locate(edit, paragraph.text, paragraph_range, document_lines)
    if isinstance(located, EditOutcome):
        return [], located
    refused = _refusal(edit, paragraph.text, located)
    if refused is not None:
        return [], refused
    planned = [
        _planned(edit, paragraph_index, paragraph, piece)
        for piece in located
        if paragraph.text[piece[0][0] : piece[0][1]] != piece[1]
    ]
    return planned, EditOutcome(edit_id=edit.id, status="applied")
