"""A run of blank lines is not a section.

`split_into_sections` maps each block back to line numbers by searching for its
text in the document. A block that is entirely whitespace strips to `""`, and
`str.find("")` succeeds at the search offset — so the block was reported as
spanning from line 1 to the end of the document. `claim_reference_validation_v2`
scopes its analysis per section, so that bogus first section silently duplicated
the whole document.
"""

from lib.services.document_sections import (
    find_text_line_range,
    split_into_sections,
)


class TestFindTextLineRange:
    def test_empty_needle_is_treated_as_not_found(self):
        """Not (1, EOF): an empty string has no location in the document."""
        assert find_text_line_range("a\nb\nc\nd\ne\n", "", 0) == (1, 1, 0)

    def test_whitespace_only_needle_is_treated_as_not_found(self):
        assert find_text_line_range("a\nb\nc\nd\ne\n", "   \n  ", 0) == (1, 1, 0)

    def test_a_real_needle_still_resolves(self):
        start, end, _ = find_text_line_range("a\nb\nc\nd\ne\n", "c", 0)
        assert (start, end) == (3, 3)

    def test_the_search_offset_is_returned_unchanged_for_an_empty_needle(self):
        """Callers thread the offset through successive searches."""
        assert find_text_line_range("a\nb\nc\n", "", 4) == (1, 1, 4)


class TestSplitIntoSections:
    def test_blank_pre_heading_region_yields_no_section(self):
        markdown = (
            "\n\n\n# Heading One\n\nSome real content here.\n\n"
            "# Heading Two\n\nMore content.\n"
        )

        sections = split_into_sections(markdown)

        assert [s.headings for s in sections] == [["Heading One"], ["Heading Two"]]
        # None of them may span the whole document.
        assert all(s.end_line < len(markdown.split("\n")) for s in sections[:1])

    def test_real_pre_heading_content_is_still_kept(self):
        """Only *blank* leading regions are dropped, not genuine preamble."""
        markdown = "Preamble sentence.\n\n# Heading One\n\nBody.\n"

        sections = split_into_sections(markdown)

        assert sections[0].headings == []
        assert sections[0].start_line == 1
        assert len(sections) == 2

    def test_section_indices_stay_contiguous_after_a_block_is_skipped(self):
        markdown = "\n\n# A\n\nalpha\n\n# B\n\nbeta\n"

        sections = split_into_sections(markdown)

        assert [s.section_index for s in sections] == list(range(len(sections)))
