"""Placing a quote that carries footnote references.

An edit quotes the markdown, where MarkItDown writes a footnote reference as a
link (`[[38]](#footnote-39)`), so the edit's rendered `display_text` reads
``closely,[38]``. Word carries the reference as a mark with no characters in
the paragraph's text, so that quote never matches as written.

The reference also has to survive the redline, and a redline cannot cross it:
docx-editor writes the replacement in one piece and leaves the mark behind it,
so ``closely,[38] and reporting requirements vary`` rewritten whole comes out
with footnote 38 after ``vary``. So the quote is cut at its references, and
each stretch between them that the edit changes becomes a redline of its own,
which leaves every mark where Word keeps it. The replacement has to carry the
same references in the same order: an edit that adds or drops one changes the
footnotes, and the export cannot write that. One that only moves a reference
through the words still works: the stretches on either side are rewritten and
the mark, which stays put, ends up where the replacement has it.
"""

from pydantic import BaseModel

from lib.models.issue_edit import IssueEdit
from lib.services.docx.edit_text import UNCHANGED_ONCE_RENDERED
from lib.services.docx.tracked_changes.lines import footnote_references
from lib.services.text.location import locate_in_paragraph, normalize_whitespace
from lib.services.text.markdown_rendering import render_line_text

FOOTNOTES_CHANGED = (
    "it adds or removes a footnote reference, which the export cannot write"
)
INSERTS_AT_FOOTNOTE = (
    "it inserts text beside a footnote reference with no quoted words there "
    "to anchor the insertion to"
)

AMBIGUOUS_LABEL = (
    "a footnote reference's number also appears as text in the quote, so the "
    "reference cannot be told apart from it"
)
SPACE_AROUND_FOOTNOTE = (
    "it changes the spacing at a footnote reference that has spaces on both "
    "sides, and the export cannot tell which side of the reference they sit on"
)


class FootnotePiece(BaseModel):
    """One redline of a footnote-carrying edit: a paragraph span and its text."""

    span: tuple[int, int]
    replace_with: str


class FootnotePlacement(BaseModel):
    """Where a footnote-carrying quote's redlines go, or why they cannot go.

    With no `pieces` and no `detail`, the quote is simply not in the paragraph.
    """

    pieces: list[FootnotePiece] = []
    detail: str | None = None


def carries_footnotes(edit: IssueEdit) -> bool:
    """Whether the edit's quote holds a footnote reference."""
    return bool(footnote_references(edit.original_text))


def _split_at(text: str, markers: list[str]) -> list[str] | None:
    """`text` cut at each rendered marker, in order; None if one is missing."""
    pieces: list[str] = []
    rest = text
    for marker in markers:
        head, found, rest = rest.partition(marker)
        if not found:
            return None
        pieces.append(head)
    pieces.append(rest)
    return pieces


def _quoted_pieces(edit: IssueEdit, markers: list[str]) -> list[str] | None:
    """`display_text` cut at the markers, with the quote's own edge whitespace.

    `display_text` is whitespace-normalized; the raw quote still says which
    spaces at its ends it owns, as `placement._with_boundary_whitespace` reads
    it, and the first and last stretch need that to be redlined the same way.
    """
    pieces = _split_at(edit.display_text, markers)
    if pieces is None:
        return None
    if edit.original_text[:1].isspace():
        pieces[0] = " " + pieces[0]
    if edit.original_text[-1:].isspace():
        pieces[-1] = pieces[-1] + " "
    return pieces


def _piece_spans(
    paragraph_text: str, quote_span: tuple[int, int], pieces: list[str]
) -> list[tuple[int, int] | None] | None:
    """Where each stretch sits inside the paragraph's match of the whole quote.

    Each is found after the one before it, inside the quote's own span, so a
    stretch that repeats elsewhere in the paragraph is never picked. A stretch
    of nothing but whitespace has no span of its own.
    """
    cursor, limit = quote_span
    spans: list[tuple[int, int] | None] = []
    for piece in pieces:
        needle = normalize_whitespace(piece)
        if not needle:
            spans.append(None)
            continue
        found = locate_in_paragraph(paragraph_text[cursor:limit], needle)
        if not found:
            return None
        start, end = found[0][0] + cursor, found[0][1] + cursor
        spans.append((start, end))
        cursor = end
    return spans


def _piece(
    span: tuple[int, int],
    bounds: tuple[int, int],
    paragraph_text: str,
    quoted: str,
    replacement: str,
) -> FootnotePiece:
    """One stretch's redline, with whitespace handled the way a quote's is.

    Whitespace both sides open or close with stays put, so it is left out of
    the redline. Whitespace only the quote has is deleted with it: the span
    grows over the paragraph's own run there, so no double space is left --
    but never past `bounds`, the neighbouring stretches, so two redlines of
    one edit never share a character.
    """
    (start, end), (floor, ceiling) = span, bounds
    if quoted[:1].isspace() and replacement[:1].isspace():
        replacement = replacement.lstrip()
    elif quoted[:1].isspace():
        while start > floor and paragraph_text[start - 1].isspace():
            start -= 1
    if quoted[-1:].isspace() and replacement[-1:].isspace():
        replacement = replacement.rstrip()
    elif quoted[-1:].isspace():
        while end < ceiling and paragraph_text[end].isspace():
            end += 1
    return FootnotePiece(span=(start, end), replace_with=replacement)


def _bounds(
    spans: list[tuple[int, int] | None], index: int, floor: int, ceiling: int
) -> tuple[int, int]:
    """How far stretch `index` may grow: up to its located neighbours."""
    before = [span[1] for span in spans[:index] if span is not None]
    after = [span[0] for span in spans[index + 1 :] if span is not None]
    return (max([floor, *before]), min([ceiling, *after]))


def _differs(quoted: str, replacement: str) -> bool:
    """Whether the edit changes a stretch, whitespace at its edges included.

    Inside the stretch only the words count: `display_text` is
    whitespace-normalized and the replacement is not, so a non-breaking space
    the replacement kept is no change. At the edges, next to a mark, gaining or
    losing a space is one: ``foo [1]bar`` to ``foo[1] bar`` moves the mark
    across the space.
    """
    return (
        normalize_whitespace(quoted) != normalize_whitespace(replacement)
        or quoted[:1].isspace() != replacement[:1].isspace()
        or quoted[-1:].isspace() != replacement[-1:].isspace()
    )


def _labels_unambiguous(texts: list[str], markers: list[str]) -> bool:
    """Whether each marker's rendered label occurs only where a marker is.

    A literal citation can read like a reference: ``See [1][[1]](#footnote-2)``
    renders as ``See [1][1]``, and cutting at the first ``[1]`` would put the
    boundary on the citation, so a redline would cross the real reference.
    """
    return all(
        text.count(label) == markers.count(label)
        for text in texts
        for label in set(markers)
    )


def _grows_across_mark(quoted: list[str], replaced: list[str], index: int) -> bool:
    """Whether stretch `index` would take whitespace that may lie past a mark.

    Word keeps no character for a reference, so ``Alpha [1] beta`` is one run
    of whitespace in the paragraph with the mark somewhere inside it. A stretch
    deleting its own space next to the mark would grow over the whole run, and
    the redline would cross the mark. Only when the stretch across the mark has
    no whitespace on that side is the run all its own.
    """
    old, new = quoted[index], replaced[index]
    leading = index > 0 and old[:1].isspace() and not new[:1].isspace()
    trailing = index < len(quoted) - 1 and old[-1:].isspace() and not new[-1:].isspace()
    return (leading and quoted[index - 1][-1:].isspace()) or (
        trailing and quoted[index + 1][:1].isspace()
    )


def place_around_footnotes(edit: IssueEdit, paragraph_text: str) -> FootnotePlacement:
    """The redlines for a quote whose footnote references the paragraph lacks.

    The quote is matched whole with its references taken out, and must be
    unique in the paragraph: `display_occurrence` was counted with them in, so
    it cannot settle a repeat here. Then each stretch between references that
    the edit changes becomes one piece.
    """
    raw = footnote_references(edit.original_text)
    if raw != footnote_references(edit.replacement_text):
        return FootnotePlacement(detail=FOOTNOTES_CHANGED)
    markers = [render_line_text(marker) for marker in raw]
    if not _labels_unambiguous([edit.display_text, edit.display_replacement], markers):
        return FootnotePlacement(detail=AMBIGUOUS_LABEL)
    quoted = _quoted_pieces(edit, markers)
    replaced = _split_at(edit.display_replacement, markers)
    if quoted is None or replaced is None:
        return FootnotePlacement()

    whole = locate_in_paragraph(paragraph_text, normalize_whitespace("".join(quoted)))
    if len(whole) != 1:
        return FootnotePlacement()
    spans = _piece_spans(paragraph_text, whole[0], quoted)
    if spans is None:
        return FootnotePlacement()

    changed = [
        index
        for index, (old, new) in enumerate(zip(quoted, replaced))
        if _differs(old, new)
    ]
    if not changed:
        return FootnotePlacement(detail=UNCHANGED_ONCE_RENDERED)
    located = [(index, span) for index in changed if (span := spans[index])]
    if len(located) != len(changed):
        return FootnotePlacement(detail=INSERTS_AT_FOOTNOTE)
    if any(_grows_across_mark(quoted, replaced, index) for index in changed):
        return FootnotePlacement(detail=SPACE_AROUND_FOOTNOTE)
    pieces: list[FootnotePiece] = []
    floor = 0
    for index, span in located:
        bounds = _bounds(spans, index, floor, len(paragraph_text))
        piece = _piece(span, bounds, paragraph_text, quoted[index], replaced[index])
        pieces.append(piece)
        floor = piece.span[1]
    return FootnotePlacement(pieces=pieces)
