"""Which span of a Word paragraph a located quote means, if any.

A proposed edit's redline and an issue's comment anchor both start from a quote
located on one markdown line (`display_text` and `display_occurrence`, settled
when the issue was reported) and need the characters of the mapped Word
paragraph it covers. Both are answered here, so the export marks the same words
for a comment as it would redline for an edit, and as the app highlights.

`resolve_quote_span` is the plain quote. `anchor_span` is the whole question
for a comment: whether the quote's line is the paragraph's own, then the span,
with a quote carrying footnote references matched around them.
"""

from collections.abc import Sequence

from lib.services.docx.tracked_changes.footnotes import (
    carries_footnotes,
    footnoted_quote_span,
)
from lib.services.docx.tracked_changes.lines import membership_refusal
from lib.services.docx.tracked_changes.models import (
    EditOutcomeStatus,
    LocatedQuoteLike,
)
from lib.services.text.location import locate_in_paragraph

# Why a repeat inside a paragraph that covers several markdown lines is left
# alone. `display_occurrence` was counted on the edit's own line, so it does
# not index the paragraph, and every way of rebasing it was wrong in a
# different way (see `resolve_quote_span`).
REPEATS_ACROSS_LINES = (
    "the quoted text repeats inside a paragraph that spans several lines "
    "of the document"
)


def _spans_several_lines(
    quote: LocatedQuoteLike,
    paragraph_range: tuple[int, int],
    document_lines: Sequence[str],
) -> bool:
    """Whether the paragraph really covers markdown lines besides the edit's.

    Measured in content, not in line numbers. The line-range mapper runs a
    paragraph's range up to the line before the next paragraph starts, and
    converted markdown puts a blank line between paragraphs -- so an ordinary
    one-line paragraph is handed the range ``(1, 2)`` with line 2 empty.
    Reading that as "several lines" would throw away `display_occurrence` on
    every paragraph in the document and report each repeated quote as
    ambiguous.
    """
    first = max(1, paragraph_range[0])
    last = min(len(document_lines), paragraph_range[1])
    return any(
        number != quote.start_line and document_lines[number - 1].strip()
        for number in range(first, last + 1)
    )


def resolve_quote_span(
    quote: LocatedQuoteLike,
    paragraph_text: str,
    paragraph_range: tuple[int, int],
    document_lines: Sequence[str],
) -> tuple[tuple[int, int] | None, EditOutcomeStatus, str | None]:
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

    A paragraph covering several markdown lines *of content* is a different
    matter -- blank separators do not count, or every paragraph in the document
    would qualify. A hard line break inside a Word paragraph converts to one
    markdown line per break, and Word keeps *nothing* where the break was -- no separator to
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
    if not quote.display_text:
        return None, "not_found", None
    spans = locate_in_paragraph(paragraph_text, quote.display_text)
    if not spans:
        return None, "not_found", None

    if _spans_several_lines(quote, paragraph_range, document_lines):
        if len(spans) == 1:
            return spans[0], "applied", None
        return None, "ambiguous", REPEATS_ACROSS_LINES

    if len(spans) == 1:
        return spans[0], "applied", None
    if quote.display_occurrence >= len(spans):
        return None, "ambiguous", None
    return spans[quote.display_occurrence], "applied", None


def anchor_span(
    quote: LocatedQuoteLike,
    paragraph_text: str,
    paragraph_range: tuple[int, int],
    document_lines: Sequence[str],
) -> tuple[int, int] | None:
    """The span of the paragraph a comment on `quote` should cover, or None.

    None whenever the redline rules would refuse to place the quote -- its line
    is not the paragraph's, the quote is not there, or it repeats where its
    occurrence cannot settle which -- so the caller falls back to the whole
    paragraph rather than mark words the app would not highlight.
    """
    if membership_refusal(quote, paragraph_text, document_lines) is not None:
        return None
    if carries_footnotes(quote):
        return footnoted_quote_span(quote, paragraph_text)
    span, _, _ = resolve_quote_span(
        quote, paragraph_text, paragraph_range, document_lines
    )
    return span
