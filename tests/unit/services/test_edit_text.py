"""Tests for what an edit's raw markdown says about whether Word can write it.

The rendered form of an edit is settled in `lib.services.markdown_text` and
checked there; what is asked here is only of the source: is the line a table
row, and can Word take the replacement as an insertion at all.
"""

from lib.services.docx.edit_text import is_table_row, unsupported_replacement_reason


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
