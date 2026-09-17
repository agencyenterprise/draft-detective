"""Tests for turning a markdown quote into the text a Word paragraph carries.

The cases mirror the frontend's `edit-highlight.test.ts`: the export and the
in-app highlight have to agree on which characters an edit covers.
"""

from lib.services.docx.edit_text import (
    all_offsets,
    is_table_row,
    locate_in_paragraph,
    source_occurrence,
    strip_markdown,
    unsupported_replacement_reason,
    word_replacement_text,
    word_search_text,
)


class TestStripMarkdown:
    def test_drops_bold_and_italic_markers(self):
        assert (
            strip_markdown("a **bold** and *slanted* and ***both*** word")
            == "a bold and slanted and both word"
        )

    def test_drops_inline_code_fences_and_strikethrough(self):
        assert (
            strip_markdown("call `run()` once, ~~twice~~") == "call run() once, twice"
        )

    def test_reduces_a_link_to_its_label(self):
        assert (
            strip_markdown("see [the study](https://example.com/a_b) for more")
            == "see the study for more"
        )

    def test_reduces_an_image_to_its_alt_text(self):
        assert (
            strip_markdown("![Figure 1: yields](https://example.com/f1.png) shows it")
            == "Figure 1: yields shows it"
        )

    def test_drops_heading_and_blockquote_prefixes(self):
        assert strip_markdown("## Results\n> quoted line") == "Results\nquoted line"

    def test_drops_list_markers(self):
        assert (
            strip_markdown("- first\n+ second\n1. third\n2) fourth")
            == "first\nsecond\nthird\nfourth"
        )
        # A `*` bullet loses its asterisk to the emphasis pass first, so the
        # marker regex no longer sees it and the space it sat on survives.
        # Harmless: every caller reads the text through the whitespace pass.
        assert strip_markdown("* starred") == " starred"
        assert word_search_text("* starred") == "starred"

    def test_keeps_snake_case_underscores_but_strips_emphasis_ones(self):
        assert (
            strip_markdown("the _stressed_ value of snake_case_name stays")
            == "the stressed value of snake_case_name stays"
        )

    def test_reduces_a_footnote_link_to_its_bracketed_label(self):
        assert (
            strip_markdown("second cohort [[1]](#footnote-2).") == "second cohort [1]."
        )
        assert (
            strip_markdown("see [the [inner] note](http://x) now")
            == "see the [inner] note now"
        )
        assert strip_markdown("![fig [a]](img.png) caption") == "fig [a] caption"

    def test_decodes_backslash_escapes_to_the_character_word_shows(self):
        assert strip_markdown("the foo\\_bar variable") == "the foo_bar variable"
        assert strip_markdown("a literal \\*star\\* here") == "a literal *star* here"
        assert (
            strip_markdown("\\[not a link\\] and 10\\. items")
            == "[not a link] and 10. items"
        )
        assert strip_markdown("C\\# and a\\|b") == "C# and a|b"

    def test_leaves_an_unescaped_backslash_before_a_letter_alone(self):
        assert strip_markdown("path C:\\Users stays") == "path C:\\Users stays"

    def test_keeps_a_mid_line_number_that_only_looks_like_a_list_marker(self):
        assert (
            strip_markdown("2019. Annual report", at_line_start=False)
            == "2019. Annual report"
        )
        assert strip_markdown("1. First item") == "First item"

    def test_keeps_a_mid_line_hash_and_arrow_too(self):
        assert strip_markdown("# 3 of 4", at_line_start=False) == "# 3 of 4"
        assert strip_markdown("> 5 mg", at_line_start=False) == "> 5 mg"

    def test_still_strips_the_emphasis_of_a_mid_line_quote(self):
        assert (
            strip_markdown("2019. **Annual** report", at_line_start=False)
            == "2019. Annual report"
        )


class TestWordSearchText:
    def test_strips_markdown_and_normalizes_whitespace_together(self):
        assert (
            word_search_text(
                "  **The   claim**\n  is [unproven](https://example.com).  "
            )
            == "The claim is unproven."
        )

    def test_an_empty_quote_yields_nothing_to_search_for(self):
        assert word_search_text("   ") == ""

    def test_passes_the_line_start_flag_through_to_the_stripping(self):
        assert word_search_text("2019. Annual report", at_line_start=False) == (
            "2019. Annual report"
        )
        assert word_search_text("2019. Annual report") == "Annual report"


class TestWordReplacementText:
    def test_keeps_a_leading_space_the_author_asked_for(self):
        assert word_replacement_text(" word", at_line_start=False) == " word"

    def test_keeps_a_trailing_space_the_author_asked_for(self):
        assert word_replacement_text("word ", at_line_start=False) == "word "
        assert word_replacement_text(" word ", at_line_start=False) == " word "

    def test_keeps_a_double_space_between_sentences(self):
        # Word writes the inserted run verbatim, so both spaces reach the page.
        assert (
            word_replacement_text("Yield fell.  Costs rose.", at_line_start=False)
            == "Yield fell.  Costs rose."
        )
        assert word_replacement_text("   spaced", at_line_start=False) == "   spaced"

    def test_keeps_a_non_breaking_space(self):
        nbsp = "Figure\u00a03"
        assert word_replacement_text(nbsp, at_line_start=False) == nbsp

    def test_reports_a_replacement_carrying_a_tab(self):
        assert word_replacement_text("14%\t(2019)", at_line_start=False) is None
        assert unsupported_replacement_reason("14%\t(2019)") == (
            "the replacement contains a tab"
        )

    def test_strips_the_markdown_syntax_word_never_shows(self):
        assert (
            word_replacement_text("the **new** [label](http://x)", at_line_start=False)
            == "the new label"
        )

    def test_reports_a_replacement_that_would_split_the_paragraph(self):
        assert word_replacement_text("first\nsecond", at_line_start=False) is None
        assert word_replacement_text("first\r\nsecond", at_line_start=True) is None
        assert unsupported_replacement_reason("first\nsecond") == (
            "the replacement spans more than one paragraph"
        )

    def test_a_writable_replacement_has_no_reason_against_it(self):
        assert unsupported_replacement_reason("Yield fell.  Costs rose.") is None
        assert unsupported_replacement_reason("") is None

    def test_strips_a_list_marker_only_at_the_start_of_a_line(self):
        assert (
            word_replacement_text("2021. Annual report", at_line_start=False)
            == "2021. Annual report"
        )
        assert word_replacement_text("2. Second item", at_line_start=True) == (
            "Second item"
        )

    def test_an_empty_replacement_stays_empty_for_a_deletion(self):
        assert word_replacement_text("", at_line_start=False) == ""
        assert word_replacement_text(" ", at_line_start=False) == " "


class TestIsTableRow:
    def test_a_pipe_delimited_row_is_one(self):
        assert is_table_row("| Metric | Value |")
        assert is_table_row("  | Output increased by 14%. |  ")
        assert is_table_row("| --- | --- |")

    def test_the_pipe_less_gfm_variant_is_one_too(self):
        assert is_table_row("Metric | Value |")

    def test_prose_is_not_a_row(self):
        assert not is_table_row("Output increased by 14%.")
        assert not is_table_row("")
        # One pipe inside a sentence is punctuation, not a table.
        assert not is_table_row("The flag is passed as -v | --verbose in the CLI.")

    def test_a_row_is_not_confused_with_a_trailing_pipe_in_prose(self):
        assert not is_table_row("Pass the output to the next command with |")


class TestAllOffsets:
    def test_lists_every_start_offset_overlapping_ones_included(self):
        assert all_offsets("Figure 3 and Figure 3", "Figure 3") == [0, 13]
        assert all_offsets("aaa", "aa") == [0, 1]
        assert all_offsets("abc", "") == []


class TestLocateInParagraph:
    def test_returns_the_span_of_a_plain_match(self):
        assert locate_in_paragraph("The claim is unproven.", "claim is") == [(4, 12)]

    def test_matches_across_a_non_breaking_space_and_spans_the_original(self):
        paragraph = "The Energy\u00a0Supply chapter"

        (span,) = locate_in_paragraph(paragraph, "Energy Supply")

        assert paragraph[span[0] : span[1]] == "Energy\u00a0Supply"

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


class TestSourceOccurrence:
    lines = [
        "# Title",
        "",
        "Figure 3 and **Figure 3** close the section.",
        "Again Figure 3 appears here.",
    ]

    def test_tells_a_formatted_quote_apart_from_an_identical_plain_one(self):
        assert source_occurrence(self.lines, 3, 3, 3, "**Figure 3**") == 1
        assert source_occurrence(self.lines, 3, 3, 3, "Figure 3 and") == 0

    def test_counts_occurrences_on_earlier_lines_of_the_block(self):
        assert source_occurrence(self.lines, 3, 4, 4, "Again Figure 3") == 0
        # Unique on its own line, third time the block shows it.
        assert source_occurrence(self.lines, 3, 4, 4, "Figure 3") == 2

    def test_gives_up_when_the_quote_is_not_unique_on_its_line(self):
        assert source_occurrence(self.lines, 3, 3, 3, "Figure 3") is None

    def test_gives_up_when_the_line_is_missing(self):
        assert source_occurrence(self.lines, 3, 3, 40, "Figure 3") is None

    def test_matches_the_quote_despite_whitespace_drift(self):
        drifted = ["Energy\u00a0Supply and **Energy Supply** again."]

        assert source_occurrence(drifted, 1, 1, 1, "**Energy Supply**") == 1
