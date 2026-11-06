"""Locating an agent-quoted span inside the document under review.

An agent quotes the document twice over: the passage an issue is about, and the
text a proposed edit replaces. Either quote has to be found in the document
before the issue can be recorded, and both are found the same way, by
`match_quote`. The DOCX converter
emits one markdown line per Word paragraph, so a quote is looked up one line at
a time and a quote is always anchored to a single line.

Matching is whitespace-normalized on both sides because the document and the
quote drift at the character level: about half of the converted DOCX documents
carry non-breaking spaces inside prose (``Energy\\xa0Supply``), and double
spaces appear before footnote markers and bold runs. A model quoting that text
back writes ordinary single spaces, so an exact comparison would fail on lines
that are otherwise quoted correctly.

Pure functions only: no document loading and no tool plumbing, so the matching
rules can be unit-tested on plain strings.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from lib.services.text.location import locate_in_paragraph, normalize_whitespace
from lib.services.text.markdown_rendering import rendered_span

# How much of the issue's line range to quote back when a lookup fails. Enough
# for the agent to re-quote from, short enough not to flood the tool result.
_EXCERPT_LIMIT = 400


def document_lines(document_text: str) -> list[str]:
    """Split a document into lines the way the agent's file backend numbers them.

    Only ``\n`` ends a line. ``str.splitlines`` would also break on form feeds
    and Unicode separators such as U+2028, which survive DOCX conversion inside
    a paragraph; the agent reads the file split on ``\n`` alone, so splitting
    any other way here would shift every line number after such a character
    and reject quotes that are correctly placed.
    """
    return document_text.split("\n")


def _clamped_range(
    lines: Sequence[str], start_line: int, end_line: int
) -> tuple[int, int]:
    """Clamp a 1-indexed inclusive line range to the document's own bounds."""
    first = max(1, start_line)
    last = min(len(lines), end_line)
    return first, last


def _count_occurrences(haystack: str, needle: str) -> int:
    """Count every occurrence of `needle`, overlapping ones included."""
    count = 0
    position = haystack.find(needle)
    while position != -1:
        count += 1
        position = haystack.find(needle, position + 1)
    return count


def find_quote_lines(
    lines: Sequence[str], start_line: int, end_line: int, quote: str
) -> list[int]:
    """Return the 1-indexed line of every occurrence of `quote` within a range.

    Each line is compared on its own after whitespace normalization, so a quote
    never matches across lines. A line that contains the quote twice is listed
    twice, so an ambiguous quote is never silently resolved.
    """
    needle = normalize_whitespace(quote)
    if not needle:
        return []

    first, last = _clamped_range(lines, start_line, end_line)
    found: list[int] = []
    for number in range(first, last + 1):
        occurrences = _count_occurrences(
            normalize_whitespace(lines[number - 1]), needle
        )
        found.extend([number] * occurrences)
    return found


def range_excerpt(
    lines: Sequence[str], start_line: int, end_line: int, limit: int = _EXCERPT_LIMIT
) -> str:
    """Quote a line range back to the agent so it can re-quote from the document."""
    first, last = _clamped_range(lines, start_line, end_line)
    if first > last:
        return ""
    text = normalize_whitespace("\n".join(lines[first - 1 : last]))
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


class QuoteMatch(BaseModel):
    """Where a quote sits: its line, its raw span there, and its rendered form."""

    line: int
    start: int
    end: int
    display_text: str
    display_occurrence: int


def match_quote(
    lines: Sequence[str],
    quote: str,
    subject: str,
    start_line: int,
    end_line: int,
    repeat_advice: str,
    not_found_advice: str = "",
) -> QuoteMatch | str:
    """Locate one agent quote on a single line of a range, or say what is wrong.

    `subject` names the quote in the message (``"edit 2: original_text"``,
    ``"passage"``), and `repeat_advice` ends the message for a quote that
    repeats, since what to do about it depends on what the quote is for;
    `not_found_advice`, when given, ends the message for one that is missing.

    The rendered form is settled here, once, and stored with the quote: the
    in-app highlight and the DOCX export both look for the characters the
    reader sees, and neither should have to re-derive them from the markdown.
    """
    if not quote.strip():
        return f"{subject} must not be blank."
    # The app renders `$$...$$` as MathML and Word holds an equation as OMML
    # with no delimiters, so neither surface has characters to find.
    if "$$" in quote:
        return (
            f"{subject} must not contain display math (`$$...$$`); the "
            "export cannot place equations."
        )

    matches = find_quote_lines(lines, start_line, end_line, quote)
    if not matches:
        return (
            f"{subject} was not found on any single line of lines "
            f"{start_line}-{end_line}. Quote it verbatim from one line of the "
            f"document. Lines {start_line}-{end_line} read: "
            f"{range_excerpt(lines, start_line, end_line)!r}"
            + (f" {not_found_advice}" if not_found_advice else "")
        )
    if len(matches) > 1:
        return (
            f"{subject} appears {len(matches)} times in lines "
            f"{start_line}-{end_line}. {repeat_advice}"
        )
    line = matches[0]

    spans = locate_in_paragraph(lines[line - 1], normalize_whitespace(quote))
    rendered = (
        rendered_span(lines[line - 1], spans[0][0], spans[0][1])
        if len(spans) == 1
        else None
    )
    if rendered is None:
        return (
            f"{subject} must start and end on plain text, not inside a link "
            "address or a formatting marker. Quote whole words from the line, "
            "including any markup that surrounds them."
        )
    return QuoteMatch(
        line=line,
        start=spans[0][0],
        end=spans[0][1],
        display_text=rendered.display_text,
        display_occurrence=rendered.display_occurrence,
    )
