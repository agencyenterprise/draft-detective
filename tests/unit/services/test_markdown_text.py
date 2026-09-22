"""Tests for rendering a markdown line into the characters a reader sees.

One CommonMark parser settles what the in-app highlight paints and what the
DOCX export searches for, so these cases are the contract both of them rest on.
"""

from lib.services.markdown_text import (
    all_offsets,
    link_destinations,
    locate_in_paragraph,
    render_line_text,
    render_replacement_text,
    rendered_span,
)


class TestRenderLineText:
    def test_drops_emphasis_delimiters(self):
        assert (
            render_line_text("a **bold** and *slanted* and ***both*** word")
            == "a bold and slanted and both word"
        )

    def test_drops_code_fences_and_strikethrough(self):
        assert (
            render_line_text("call `run()` once, ~~twice~~") == "call run() once, twice"
        )

    def test_keeps_the_contents_of_a_code_span_exactly(self):
        assert render_line_text("`**name**`") == "**name**"
        assert render_line_text("`a_b`") == "a_b"
        assert (
            render_line_text("the `**flag**` and **bold**") == "the **flag** and bold"
        )

    def test_leaves_a_backtick_with_no_closing_partner_alone(self):
        assert render_line_text("a ` b") == "a ` b"

    def test_reduces_a_link_to_its_label(self):
        assert (
            render_line_text("see [the study](https://example.com/a_b) for more")
            == "see the study for more"
        )

    def test_reduces_an_image_to_its_alt_text(self):
        assert (
            render_line_text("![Figure 1: yields](https://example.com/f1.png) shows it")
            == "Figure 1: yields shows it"
        )

    def test_reduces_a_footnote_link_to_its_bracketed_label(self):
        assert (
            render_line_text("second cohort [[1]](#footnote-2) in 2019.")
            == "second cohort [1] in 2019."
        )

    def test_drops_a_heading_hash_and_a_blockquote_arrow(self):
        assert render_line_text("## Results") == "Results"
        assert render_line_text("> quoted line") == "quoted line"

    def test_drops_a_list_marker_at_the_head_of_the_line(self):
        assert render_line_text("- **Output** increased") == "Output increased"
        assert render_line_text("1. First item") == "First item"
        assert render_line_text("* starred") == "starred"

    def test_keeps_a_mid_line_number_that_only_looks_like_a_list_marker(self):
        assert (
            render_line_text("Smith et al. 2019. Annual report.")
            == "Smith et al. 2019. Annual report."
        )

    def test_keeps_a_star_that_emphasizes_nothing(self):
        assert render_line_text("2 * 3 = 6") == "2 * 3 = 6"
        assert render_line_text("5*3 and 2 ** 3") == "5*3 and 2 ** 3"

    def test_keeps_an_underscore_that_emphasizes_nothing(self):
        assert (
            render_line_text("_private and snake_case_name stay")
            == "_private and snake_case_name stay"
        )

    def test_drops_an_underscore_that_does_emphasize(self):
        assert render_line_text("the _stressed_ value") == "the stressed value"
        assert render_line_text("__strong__ here") == "strong here"

    def test_decodes_backslash_escapes_to_the_character_word_shows(self):
        assert render_line_text("the foo\\_bar variable") == "the foo_bar variable"
        assert render_line_text("a literal \\*star\\* here") == "a literal *star* here"
        assert (
            render_line_text("\\[not a link\\] and 10\\. items")
            == "[not a link] and 10. items"
        )
        assert render_line_text("C\\# and a\\|b") == "C# and a|b"

    def test_leaves_an_unescaped_backslash_before_a_letter_alone(self):
        assert render_line_text("path C:\\Users stays") == "path C:\\Users stays"

    def test_leaves_the_line_s_own_whitespace_alone(self):
        assert render_line_text("The  Energy\u00a0Supply   chapter") == (
            "The  Energy\u00a0Supply   chapter"
        )

    def test_a_lone_table_row_renders_as_the_prose_it_looks_like(self):
        # Not a GFM table without its delimiter row, and an edit anchored to a
        # row is refused before its text is compared to anything.
        assert render_line_text("| Metric | Value |") == "| Metric | Value |"


class TestRenderedSpan:
    def test_tells_a_formatted_quote_apart_from_an_identical_plain_one(self):
        line = "Figure 3 and **Figure 3** close the section."

        span = rendered_span(line, line.index("**"), line.index("**") + 12)

        assert span is not None
        assert (span.display_text, span.display_occurrence) == ("Figure 3", 1)

    def test_a_plain_quote_before_the_repeat_is_the_first_occurrence(self):
        line = "Figure 3 and **Figure 3** close the section."

        span = rendered_span(line, 0, len("Figure 3 and"))

        assert span is not None
        assert (span.display_text, span.display_occurrence) == ("Figure 3 and", 0)

    def test_a_quote_covering_a_link_reduces_to_its_label(self):
        line = "See the [Wrong report](https://x/wrong) for details."

        span = rendered_span(line, line.index("["), line.index(")") + 1)

        assert span is not None
        assert (span.display_text, span.display_occurrence) == ("Wrong report", 0)

    def test_a_quote_ending_inside_a_link_address_has_no_rendered_span(self):
        line = "See [the study](https://example.com/a_b) for more"

        assert rendered_span(line, 4, 25) is None

    def test_a_quote_covering_a_footnote_reference_keeps_its_label(self):
        line = "second cohort [[1]](#footnote-2) in 2019."

        span = rendered_span(line, 0, len("second cohort [[1]](#footnote-2)"))

        assert span is not None
        assert span.display_text == "second cohort [1]"

    def test_a_quote_opening_a_list_item_loses_the_marker(self):
        # Marked at its end only: an opening mark in front of the bullet would
        # stop the line being a list item at all.
        line = "- **Output** increased"

        span = rendered_span(line, 0, len(line))

        assert span is not None
        assert (span.display_text, span.display_occurrence) == ("Output increased", 0)

    def test_a_quote_opening_with_a_mid_line_year_keeps_it(self):
        line = "Smith et al. 2019. Annual report."

        span = rendered_span(line, 13, len(line) - 1)

        assert span is not None
        assert span.display_text == "2019. Annual report"

    def test_boundary_whitespace_is_left_to_the_caller(self):
        line = "This is a bad result."

        span = rendered_span(line, line.index(" bad "), line.index(" bad ") + 5)

        assert span is not None
        assert span.display_text == "bad"

    def test_a_quote_that_renders_to_nothing_has_no_span(self):
        assert rendered_span("![a figure](f1.png) and more", 0, 19) is not None
        assert rendered_span("**bold**", 0, 2) is None

    def test_an_impossible_range_has_no_span(self):
        assert rendered_span("a line", 4, 2) is None
        assert rendered_span("a line", 0, 0) is None
        assert rendered_span("a line", 0, 99) is None


class TestRenderReplacementText:
    def test_keeps_the_whitespace_the_author_asked_for(self):
        assert render_replacement_text(" good ") == " good "
        assert render_replacement_text("   spaced") == "   spaced"
        assert render_replacement_text("Yield fell.  Costs rose.") == (
            "Yield fell.  Costs rose."
        )
        assert render_replacement_text("Figure\u00a03") == "Figure\u00a03"

    def test_an_empty_replacement_stays_empty_for_a_deletion(self):
        assert render_replacement_text("") == ""
        assert render_replacement_text(" ") == " "

    def test_keeps_a_literal_star(self):
        assert render_replacement_text("2 * 3") == "2 * 3"
        assert render_replacement_text("a * b * c") == "a * b * c"

    def test_drops_the_syntax_the_document_never_shows(self):
        assert render_replacement_text("**bold**") == "bold"
        assert render_replacement_text("the **new** [label](http://x)") == (
            "the new label"
        )

    def test_a_leading_numeral_is_not_a_list_marker(self):
        # A replacement is usually a fragment of a paragraph, never a block.
        assert render_replacement_text("2021. Annual report") == "2021. Annual report"
        assert render_replacement_text("2. Second item") == "2. Second item"

    def test_a_mid_line_hash_stays_in_the_text(self):
        assert render_replacement_text("C# and a note") == "C# and a note"


class TestRenderReplacementTextInBlockContext:
    """A quote starting at column 0 takes its line's block syntax with it, and
    the replacement was written carrying the same syntax."""

    def test_a_heading_replacement_loses_its_hashes(self):
        assert (
            render_replacement_text("# New heading", block_context=True)
            == "New heading"
        )
        assert (
            render_replacement_text("### New heading", block_context=True)
            == "New heading"
        )

    def test_a_list_item_replacement_loses_its_marker(self):
        assert render_replacement_text("- item two", block_context=True) == "item two"
        assert (
            render_replacement_text("2. Second item", block_context=True)
            == "Second item"
        )

    def test_a_replacement_with_no_block_syntax_is_unchanged(self):
        assert (
            render_replacement_text("New heading", block_context=True) == "New heading"
        )
        assert render_replacement_text("C# and a note", block_context=True) == (
            "C# and a note"
        )

    def test_the_whitespace_the_edit_asked_for_is_put_back(self):
        # Block parsing trims a paragraph's edges; the edit meant those spaces.
        assert render_replacement_text("# New heading ", block_context=True) == (
            "New heading "
        )
        assert render_replacement_text(" Yields ", block_context=True) == " Yields "
        assert render_replacement_text("  ", block_context=True) == "  "
        assert render_replacement_text("", block_context=True) == ""

    def test_inner_whitespace_is_kept(self):
        assert render_replacement_text("# A  B", block_context=True) == "A  B"


class TestLinkDestinations:
    def test_lists_every_destination_in_order(self):
        assert link_destinations("see [a](http://x) and [b](http://y)") == [
            "http://x",
            "http://y",
        ]

    def test_an_image_destination_counts_too(self):
        assert link_destinations("![fig](f1.png)") == ["f1.png"]

    def test_text_without_links_has_none(self):
        assert link_destinations("no links here") == []
        assert link_destinations("brackets [only] and (parens)") == []

    def test_a_label_change_leaves_the_destination_alone(self):
        assert link_destinations("[Wrong report](https://x/a)") == link_destinations(
            "[Correct report](https://x/a)"
        )
        assert link_destinations("[Report](https://x/a)") != link_destinations(
            "[Report](https://x/b)"
        )

    def test_a_destination_holding_balanced_parentheses_is_read_whole(self):
        assert link_destinations("[a](https://x/(1))") == ["https://x/(1)"]
        assert link_destinations("[a](https://x/(1)/end)") == ["https://x/(1)/end"]

    def test_two_destinations_differing_inside_the_parentheses_are_not_equal(self):
        # A pattern stopping at the first `)` reads both as `https://x/(1`
        # and would let the retarget through.
        assert link_destinations("[a](https://x/(1))") != link_destinations(
            "[a](https://x/(2))"
        )

    def test_a_link_inside_a_code_span_is_not_a_link(self):
        assert link_destinations("`[x](y)` is the syntax") == []

    def test_a_footnote_reference_carries_its_destination(self):
        assert link_destinations("cohort [[1]](#footnote-2)") == ["#footnote-2"]


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
