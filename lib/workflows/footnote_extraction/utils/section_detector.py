"""Section detection utilities for footnote extraction."""

import re
from typing import List, Optional

from lib.workflows.footnote_extraction.state import FootnoteSection

# Patterns for detecting footnote entries at start of line
FOOTNOTE_PATTERNS = [
    re.compile(r"^\d+\.\s+"),  # "1. Text"
    re.compile(r"^\[\d+\]\s+"),  # "[1] Text"
    re.compile(r"^\^\d+\s+"),  # "^1 Text"
]


def _matches_footnote_pattern(line: str) -> bool:
    """
    Check if a line matches any footnote pattern.

    Args:
        line: The line to check

    Returns:
        True if line starts with a footnote marker pattern
    """
    return any(pattern.match(line) for pattern in FOOTNOTE_PATTERNS)


def _calculate_char_offset(lines: List[str], line_index: int) -> int:
    """
    Calculate character offset for a given line index.

    Args:
        lines: List of all lines in the document
        line_index: Index of the line to calculate offset for

    Returns:
        Character offset from start of document
    """
    # Sum lengths of all lines before this one, including newlines
    return sum(len(line) + 1 for line in lines[:line_index])


def detect_footnote_region(markdown: str) -> List[FootnoteSection]:
    """
    Detect footnote region at the end of the document.

    Scans backwards from the document end looking for numbered entries.
    Footnotes appear as a numbered list at document end without a section heading.

    The algorithm looks for lines matching "N. Text [↑](#footnote-ref-M)" pattern
    and finds the lowest numbered footnote to determine the start of the section.

    Args:
        markdown: Full document markdown text

    Returns:
        List containing a single FootnoteSection if found, empty list otherwise
    """
    if not markdown:
        return []

    lines = markdown.split("\n")

    # Pattern to match footnote with back-reference link
    # e.g., "1. Text [↑](#footnote-ref-2)"
    footnote_with_ref_pattern = re.compile(
        r"^(\d+)\.\s+.*\[↑\]\(#footnote-ref-\d+\)"
    )

    # Find all lines that match the footnote pattern
    footnote_matches = []
    for i, line in enumerate(lines):
        match = footnote_with_ref_pattern.match(line.strip())
        if match:
            footnote_number = int(match.group(1))
            footnote_matches.append((i, footnote_number))

    if not footnote_matches:
        return []

    # Find the line with the smallest footnote number
    # This is likely the start of the footnote section
    min_line_index = min(footnote_matches, key=lambda x: x[1])[0]

    start_offset = _calculate_char_offset(lines, min_line_index)
    end_offset = len(markdown)

    return [FootnoteSection(start_offset=start_offset, end_offset=end_offset)]
