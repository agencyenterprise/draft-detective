"""Locating an agent-quoted span inside the document under review.

An agent proposing an edit quotes the text it wants replaced; that quote has to
be found in the document before the edit can be recorded. The DOCX converter
emits one markdown line per Word paragraph, so a quote is looked up one line at
a time and an edit is always anchored to a single line.

Matching is whitespace-normalized on both sides because the document and the
quote drift at the character level: about half of the converted DOCX documents
carry non-breaking spaces inside prose (``Energy\\xa0Supply``), and double
spaces appear before footnote markers and bold runs. A model quoting that text
back writes ordinary single spaces, so an exact comparison would fail on lines
that are otherwise quoted correctly.

Pure functions only: no document loading and no tool plumbing, so the matching
rules can be unit-tested on plain strings.
"""

import re
from typing import List, Sequence, Tuple

_WHITESPACE_RUN = re.compile(r"\s+")

# How much of the issue's line range to quote back when a lookup fails. Enough
# for the agent to re-quote from, short enough not to flood the tool result.
_EXCERPT_LIMIT = 400


def document_lines(document_text: str) -> List[str]:
    """Split a document into lines the way the agent's file backend numbers them.

    Only ``\n`` ends a line. ``str.splitlines`` would also break on form feeds
    and Unicode separators such as U+2028, which survive DOCX conversion inside
    a paragraph; the agent reads the file split on ``\n`` alone, so splitting
    any other way here would shift every line number after such a character
    and reject quotes that are correctly placed.
    """
    return document_text.split("\n")


def normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (non-breaking spaces included) to one space."""
    return _WHITESPACE_RUN.sub(" ", text).strip()


def _clamped_range(
    lines: Sequence[str], start_line: int, end_line: int
) -> Tuple[int, int]:
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
) -> List[int]:
    """Return the 1-indexed line of every occurrence of `quote` within a range.

    Each line is compared on its own after whitespace normalization, so a quote
    never matches across lines. A line that contains the quote twice is listed
    twice, so an ambiguous quote is never silently resolved.
    """
    needle = normalize_whitespace(quote)
    if not needle:
        return []

    first, last = _clamped_range(lines, start_line, end_line)
    found: List[int] = []
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
