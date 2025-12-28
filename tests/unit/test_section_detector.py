"""Unit tests for section detection utilities."""

import pytest

from lib.workflows.reference_extraction.utils.section_detector import (
    extract_headings,
    _group_consecutive_indices,
    HeadingInfo,
)


class TestExtractHeadings:
    """Tests for extract_headings function."""

    def test_extracts_all_headings(self):
        """Should extract all markdown headings."""
        markdown = """# Introduction

Some text.

## Methods

More text.

## References

1. Smith (2020).
"""
        headings = extract_headings(markdown)
        assert len(headings) == 3
        assert headings[0].text == "Introduction"
        assert headings[1].text == "Methods"
        assert headings[2].text == "References"

    def test_captures_heading_levels(self):
        """Should capture correct heading levels."""
        markdown = """# H1

## H2

### H3
"""
        headings = extract_headings(markdown)
        assert len(headings) == 3
        assert headings[0].level == 1
        assert headings[1].level == 2
        assert headings[2].level == 3

    def test_calculates_offsets(self):
        """Should calculate correct start/end offsets."""
        markdown = """# First

Content 1.

# Second

Content 2.
"""
        headings = extract_headings(markdown)
        assert len(headings) == 2

        # First section should end where second starts
        assert headings[0].end_offset == headings[1].start_offset

        # Last section should end at document end
        assert headings[1].end_offset == len(markdown)

    def test_returns_empty_for_no_headings(self):
        """Should return empty list for document without headings."""
        markdown = """Just plain text.
No headings here.
"""
        headings = extract_headings(markdown)
        assert headings == []

    def test_returns_empty_for_empty_document(self):
        """Should return empty list for empty document."""
        assert extract_headings("") == []
        assert extract_headings(None) == []

    def test_extracts_section_content_correctly(self):
        """Should allow extracting section text using offsets."""
        markdown = """# Intro

Intro text.

# References

1. Smith (2020). Paper title.
2. Doe (2019). Another paper.
"""
        headings = extract_headings(markdown)
        assert len(headings) == 2

        # Get the references section content
        ref_heading = headings[1]
        section_text = markdown[ref_heading.start_offset : ref_heading.end_offset]
        assert "Smith (2020)" in section_text
        assert "Doe (2019)" in section_text
        assert "Intro text" not in section_text

    def test_extracts_url_as_heading(self):
        """URLs formatted as headings should be extracted (handled by classifier)."""
        markdown = """# References

Bengio, Y. (2023). How Rogue AIs May Arise.

## https://yoshuabengio.org/2023/05/22/how-rogue-ais-may-arise/

Okemwa, K. (2024). OpenAI CEO Sam Altman Says AGI.

# Conclusion

Final thoughts.
"""
        headings = extract_headings(markdown)
        assert len(headings) == 3
        assert headings[0].text == "References"
        assert headings[1].text == "https://yoshuabengio.org/2023/05/22/how-rogue-ais-may-arise/"
        assert headings[2].text == "Conclusion"


class TestGroupConsecutiveIndices:
    """Tests for _group_consecutive_indices helper."""

    def test_groups_consecutive_indices(self):
        assert _group_consecutive_indices([1, 2, 3]) == [[1, 2, 3]]
        assert _group_consecutive_indices([1, 2, 5, 6, 7]) == [[1, 2], [5, 6, 7]]
        assert _group_consecutive_indices([0, 2, 4]) == [[0], [2], [4]]

    def test_handles_single_index(self):
        assert _group_consecutive_indices([5]) == [[5]]

    def test_handles_empty_list(self):
        assert _group_consecutive_indices([]) == []

    def test_handles_duplicates(self):
        """Duplicates should be deduplicated before grouping."""
        assert _group_consecutive_indices([1, 1, 2, 2, 3]) == [[1, 2, 3]]

    def test_handles_unsorted_input(self):
        """Input should be sorted before grouping."""
        assert _group_consecutive_indices([3, 1, 2]) == [[1, 2, 3]]
        assert _group_consecutive_indices([5, 1, 2, 6]) == [[1, 2], [5, 6]]
