"""Unit tests for locating an agent-quoted span in the document markdown.

These are the pure helpers behind proposed-edit validation: they turn a quote
into a line number, so the interesting cases are whitespace drift between the
document and the quote (non-breaking and doubled spaces) and ambiguity.
"""

from lib.workflows.simple_deep_agent.edit_anchoring import (
    document_lines,
    find_quote_lines,
    normalize_whitespace,
    range_excerpt,
)

_DOCUMENT = "\n".join(
    [
        "# Title",  # 1
        "",  # 2
        "The CBT protocol was applied to every",  # 3
        "participant in the second\xa0cohort  [[1]](#footnote-2).",  # 4
        "",  # 5
        "Results appear in Figure 3 and Figure 3.",  # 6
    ]
)


def _lines() -> list[str]:
    return document_lines(_DOCUMENT)


def test_normalize_whitespace_collapses_runs_and_trims():
    assert normalize_whitespace("  a \n\t b\xa0\xa0c  ") == "a b c"


def test_document_lines_splits_on_newline_only():
    # A trailing newline yields a final empty line, exactly as the agent's file
    # backend counts it, so line numbers agree with what the agent read.
    assert document_lines("a\nb\n") == ["a", "b", ""]


def test_unicode_separators_and_form_feeds_do_not_shift_line_numbers():
    # U+2028 and \f survive DOCX conversion inside a paragraph. The agent's
    # backend keeps them on their line, so a quote after them is still on
    # line 3 -- not line 4 or 5 as str.splitlines would have numbered it.
    document = "# Title\n\nFirst\u2028clause\fthen the CBT protocol.\nNext paragraph."
    lines = document_lines(document)
    assert len(lines) == 4
    assert find_quote_lines(lines, 3, 3, "the CBT protocol") == [3]
    assert find_quote_lines(lines, 4, 4, "Next paragraph") == [4]


def test_quote_is_found_on_its_line():
    assert find_quote_lines(_lines(), 1, 6, "Figure 3 and Figure 3") == [6]


def test_quote_matches_despite_nbsp_and_double_spaces_in_the_document():
    # The converter keeps Word's non-breaking spaces and doubled spaces; the
    # agent quotes the text with ordinary single spaces.
    assert find_quote_lines(_lines(), 1, 6, "second cohort [[1]](#footnote-2)") == [4]


def test_quote_never_matches_across_lines():
    assert find_quote_lines(_lines(), 1, 6, "applied to every participant") == []


def test_quote_outside_the_range_is_not_found():
    assert find_quote_lines(_lines(), 1, 4, "Results appear") == []


def test_repeated_quote_reports_every_occurrence():
    assert find_quote_lines(_lines(), 6, 6, "Figure 3") == [6, 6]


def test_blank_quote_matches_nothing():
    assert find_quote_lines(_lines(), 1, 6, "   \n  ") == []


def test_range_is_clamped_to_the_document():
    assert find_quote_lines(_lines(), 0, 999, "# Title") == [1]


def test_inverted_range_matches_nothing():
    assert find_quote_lines(_lines(), 5, 3, "cohort") == []


def test_range_excerpt_normalizes_and_truncates():
    assert range_excerpt(_lines(), 3, 4) == (
        "The CBT protocol was applied to every participant in the second cohort "
        "[[1]](#footnote-2)."
    )
    assert range_excerpt(_lines(), 3, 4, limit=7) == "The CBT..."


def test_range_excerpt_of_an_empty_range_is_empty():
    assert range_excerpt(_lines(), 9, 12) == ""
