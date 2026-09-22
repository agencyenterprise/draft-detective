"""Tests for finding a span of text in a longer one across whitespace drift.

Every span handed back indexes the raw text, so the caller can search the
document for exactly those characters -- non-breaking spaces and all.
"""

from lib.services.text_location import all_offsets, locate_in_paragraph


class TestAllOffsets:
    def test_lists_every_start_offset_overlapping_ones_included(self):
        assert all_offsets("Figure 3 and Figure 3", "Figure 3") == [0, 13]
        assert all_offsets("aaa", "aa") == [0, 1]
        assert all_offsets("abc", "") == []


class TestLocateInParagraph:
    def test_returns_the_span_of_a_plain_match(self):
        assert locate_in_paragraph("The claim is unproven.", "claim is") == [(4, 12)]

    def test_matches_across_a_non_breaking_space_and_spans_the_original(self):
        paragraph = "The Energy Supply chapter"

        (span,) = locate_in_paragraph(paragraph, "Energy Supply")

        assert paragraph[span[0] : span[1]] == "Energy Supply"

    def test_matches_across_a_double_space_and_spans_the_original(self):
        paragraph = "as Figure  3 shows"

        (span,) = locate_in_paragraph(paragraph, "Figure 3")

        assert paragraph[span[0] : span[1]] == "Figure  3"

    def test_ignores_leading_and_trailing_whitespace_of_the_paragraph(self):
        paragraph = "\n   The  \t claim\n\n   is   unproven.  "

        (span,) = locate_in_paragraph(paragraph, "The claim is unproven.")

        assert paragraph[span[0] : span[1]] == "The  \t claim\n\n   is   unproven."

    def test_lists_every_occurrence(self):
        paragraph = "Figure 3 and Figure 3 again"

        assert locate_in_paragraph(paragraph, "Figure 3") == [(0, 8), (13, 21)]

    def test_reports_nothing_for_an_absent_or_empty_needle(self):
        assert locate_in_paragraph("The claim is unproven.", "a badger") == []
        assert locate_in_paragraph("The claim is unproven.", "") == []

    def test_is_case_sensitive(self):
        assert locate_in_paragraph("The claim", "the claim") == []
