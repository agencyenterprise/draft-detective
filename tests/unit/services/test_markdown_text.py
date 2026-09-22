"""Tests for rendering a markdown line into the characters a reader sees.

One CommonMark parser settles what the in-app highlight paints and what the
DOCX export searches for, so these cases are the contract both of them rest on.
"""

from lib.services.markdown_text import (
    link_destinations,
    render_line_text,
    rendered_replacement_in_context,
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


class TestTheMarksKeepTheirDelimiterClass:
    """A mark inserted at the quote's boundary must not change what the parser
    makes of the characters around it.

    CommonMark reads a delimiter run against the class of its neighbours, so
    each mark takes the class of the character it displaced: letter-like
    against a word character, punctuation against whitespace or punctuation.
    """

    URL = "See https://example.org/report_final_version.pdf for details."

    def test_an_intraword_underscore_does_not_start_emphasizing(self):
        # A punctuation mark beside the `_` would make the run "preceded by
        # punctuation", which is what lets `_` open: the quote came back as
        # `final` and the export would have left the underscores behind.
        start = self.URL.index("_final_")
        span = rendered_span(self.URL, start, start + len("_final_"))

        assert span is not None
        assert span.display_text == "_final_"

    def test_a_replacement_in_the_same_place_keeps_its_own_punctuation(self):
        start = self.URL.index("_final_")
        end = start + len("_final_")

        assert rendered_replacement_in_context(self.URL, start, end, "-draft-") == (
            "-draft-"
        )
        assert rendered_replacement_in_context(self.URL, start, end, "_draft_") == (
            "_draft_"
        )

    def test_an_underscore_run_at_a_word_boundary_still_emphasizes(self):
        # The other direction: a letter-like mark here would stop the run
        # opening at all and hand back `__strong__` with its delimiters.
        line = "a __strong__ b"
        span = rendered_span(line, 2, 12)

        assert span is not None
        assert span.display_text == "strong"

    def test_stars_emphasize_whatever_sits_beside_the_quote(self):
        mid = rendered_span("The **bold** word", 4, 12)
        intraword = rendered_span("a**bold**b", 1, 9)

        assert mid is not None and mid.display_text == "bold"
        assert intraword is not None and intraword.display_text == "bold"

    def test_the_underscores_a_reader_sees_are_still_kept(self):
        lone = rendered_span("the _private and x", 4, 12)
        snake = rendered_span("use snake_case_name here", 4, 19)

        assert lone is not None and lone.display_text == "_private"
        assert snake is not None and snake.display_text == "snake_case_name"

    def test_a_star_that_emphasizes_nothing_is_still_kept(self):
        span = rendered_span("yield 2 * 3 plots", 6, 11)

        assert span is not None and span.display_text == "2 * 3"

    def test_a_footnote_reference_still_reduces_to_its_label(self):
        span = rendered_span("cohort [[1]](#footnote-2) rose", 7, 25)

        assert span is not None and span.display_text == "[1]"


class TestRenderedReplacementInContext:
    """The replacement is rendered where the quote sat, not on its own: a quote
    can open or close inside formatting that carries on around it, and so can
    the replacement that takes its place."""

    def test_a_quote_ending_inside_bold_closes_the_run_it_came_from(self):
        # `old phrase**` is a legal quote whose stars are the closing half of
        # the document's bold run. Rendered alone the stars survive as
        # literals and Word is handed `new phrase**`.
        line = "The **old phrase** matters."

        assert (
            rendered_replacement_in_context(line, 6, 18, "new phrase**") == "new phrase"
        )

    def test_a_quote_inside_a_code_span_keeps_its_literal_stars(self):
        # The other direction: inside backticks nothing is emphasis, so the
        # stars have to stay. Rendered alone they would be stripped.
        line = "Set `a*b*c` now"

        assert rendered_replacement_in_context(line, 5, 10, "x*y*z") == "x*y*z"

    def test_a_whole_heading_loses_its_hashes(self):
        assert (
            rendered_replacement_in_context("# Old heading", 0, 13, "# New heading")
            == "New heading"
        )

    def test_a_whole_list_item_loses_its_marker(self):
        assert rendered_replacement_in_context("- item one", 0, 10, "- item two") == (
            "item two"
        )

    def test_a_mid_line_hash_is_not_block_syntax_and_stays(self):
        line = "The second cohort."

        assert (
            rendered_replacement_in_context(line, 4, 17, "cohort # 2") == "cohort # 2"
        )

    def test_a_mid_line_numeral_is_not_a_list_marker(self):
        line = "Smith et al. 2019. Annual report."

        assert rendered_replacement_in_context(line, 13, 32, "2021. Annual report") == (
            "2021. Annual report"
        )

    def test_the_whitespace_the_edit_asked_for_is_kept(self):
        # Written into the document verbatim, so every space reaches the page.
        line = "This is a bad result."
        assert rendered_replacement_in_context(line, 10, 13, " good ") == " good "

        joined = "This is aword."
        assert rendered_replacement_in_context(joined, 8, 13, "a  word") == "a  word"
        assert rendered_replacement_in_context(joined, 9, 13, " word") == " word"

    def test_boundary_whitespace_survives_a_block_trim(self):
        # Block parsing trims a paragraph's edges, and a quote at column 0 is
        # rendered as the block it opens.
        assert (
            rendered_replacement_in_context("Old heading", 0, 11, " New heading")
            == " New heading"
        )
        assert (
            rendered_replacement_in_context("# Old heading", 0, 13, "# New heading ")
            == "New heading "
        )

    def test_a_deletion_stays_empty_and_whitespace_stays_as_written(self):
        line = "The **old phrase** matters."

        assert rendered_replacement_in_context(line, 6, 18, "") == ""
        assert rendered_replacement_in_context(line, 6, 18, " ") == " "
        # Deleting a whole line, block syntax and all, is still a deletion.
        assert rendered_replacement_in_context("# Old heading", 0, 13, "") == ""

    def test_a_replacement_that_breaks_the_parse_has_no_text_to_write(self):
        # The quote is a parenthetical's contents, so the line's own `)` closes
        # the destination the replacement opens and swallows the closing mark
        # with it. Nothing of the replacement reaches the page as text.
        line = "The cohort (n = 40) was small."

        assert (
            rendered_replacement_in_context(line, 12, 18, "[forty](https://x") is None
        )
        # A replacement that does not open one is fine in the same place.
        assert rendered_replacement_in_context(line, 12, 18, "n = 38") == "n = 38"

    def test_a_replacement_closing_a_code_span_early_still_has_text(self):
        # Reported as a None case; it is not one. The backtick closes the span
        # early, but both marks survive and the text between them is what Word
        # should carry -- Word has no backticks, only the code formatting.
        line = "Set `a*b*c` now"

        assert rendered_replacement_in_context(line, 5, 10, "x*y*z`") == "x*y*z"

    def test_an_impossible_range_has_nothing_to_render(self):
        assert rendered_replacement_in_context("a line", 4, 2, "x") is None
        assert rendered_replacement_in_context("a line", 0, 0, "x") is None
        assert rendered_replacement_in_context("a line", 0, 99, "x") is None


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
