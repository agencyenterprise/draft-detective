"""Tests for what an edit's raw markdown says about whether Word can write it.

The rendered form of an edit is settled in `lib.services.markdown_text` and
checked there; what is asked here is only of the source: is the line a table
row, would the replacement move a hyperlink, can Word take it as an insertion
at all.
"""

from lib.services.docx.edit_text import (
    is_table_row,
    link_destinations,
    unsupported_replacement_reason,
)


class TestUnsupportedReplacementReason:
    def test_reports_a_replacement_carrying_a_tab(self):
        assert unsupported_replacement_reason("14%\t(2019)") == (
            "the replacement contains a tab"
        )

    def test_reports_a_replacement_that_would_split_the_paragraph(self):
        assert unsupported_replacement_reason("first\nsecond") == (
            "the replacement spans more than one paragraph"
        )
        assert unsupported_replacement_reason("first\r\nsecond") == (
            "the replacement spans more than one paragraph"
        )

    def test_a_writable_replacement_has_no_reason_against_it(self):
        assert unsupported_replacement_reason("Yield fell.  Costs rose.") is None
        assert unsupported_replacement_reason("") is None
        assert unsupported_replacement_reason("Figure 3") is None


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
