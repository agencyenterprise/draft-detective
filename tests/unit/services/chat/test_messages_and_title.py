"""The title cleanup rules."""

from lib.services.chat.title import FALLBACK_TITLE, MAX_TITLE_LENGTH, clean_title


class TestCleanTitle:
    def test_quotes_and_whitespace_go(self) -> None:
        assert clean_title('  "Reference check for draft"  ') == "Reference check for draft"

    def test_long_titles_are_cut(self) -> None:
        assert len(clean_title("x" * 200)) == MAX_TITLE_LENGTH

    def test_nothing_left_means_the_fallback(self) -> None:
        assert clean_title('""') == FALLBACK_TITLE
