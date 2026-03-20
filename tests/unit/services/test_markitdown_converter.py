"""Tests for the markitdown file converter post-processing."""

import pytest

from lib.services.converters.markitdown import _fix_escaped_underscores_in_urls


def test_fixes_escaped_underscore_in_https_url():
    markdown = (
        "See https://www.rand.org/pubs/research\\_reports/RR2240.html for details."
    )
    result = _fix_escaped_underscores_in_urls(markdown)
    assert (
        result
        == "See https://www.rand.org/pubs/research_reports/RR2240.html for details."
    )


def test_fixes_escaped_underscore_in_http_url():
    markdown = "Visit http://example.com/some\\_path/file.html"
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == "Visit http://example.com/some_path/file.html"


def test_fixes_multiple_escaped_underscores_in_same_url():
    markdown = "https://example.com/foo\\_bar\\_baz"
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == "https://example.com/foo_bar_baz"


def test_fixes_multiple_urls_in_same_text():
    markdown = "First: https://a.com/foo\\_bar and second: https://b.com/baz\\_qux"
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == "First: https://a.com/foo_bar and second: https://b.com/baz_qux"


def test_does_not_touch_escaped_underscores_outside_urls():
    markdown = "This is \\_italic\\_ text and https://example.com/ok"
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == "This is \\_italic\\_ text and https://example.com/ok"


def test_leaves_clean_url_unchanged():
    markdown = "See https://www.example.com/path/to/page for more."
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == markdown


def test_leaves_empty_string_unchanged():
    assert _fix_escaped_underscores_in_urls("") == ""


def test_leaves_plain_text_without_urls_unchanged():
    markdown = "No links here, just some \\_escaped\\_ underscores."
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == markdown


def test_fixes_escaped_underscore_in_markdown_link_syntax():
    markdown = "[RAND report](https://www.rand.org/pubs/research\\_reports/RR2240.html)"
    result = _fix_escaped_underscores_in_urls(markdown)
    assert (
        result
        == "[RAND report](https://www.rand.org/pubs/research_reports/RR2240.html)"
    )


def test_fixes_escaped_underscore_when_label_and_url_are_the_same():
    markdown = "[https://example.com/foo\_bar](https://example.com/foo\_bar)"
    result = _fix_escaped_underscores_in_urls(markdown)
    assert result == "[https://example.com/foo_bar](https://example.com/foo_bar)"


def test_realistic_bibliography_entry():
    markdown = (
        "Vermeer, Michael J. D., *Identifying Law Enforcement Needs*, "
        "RAND Corporation, RR-2240-NIJ, 2018. As of November 16, 2022:\n"
        "https://www.rand.org/pubs/research\\_reports/RR2240.html"
    )
    result = _fix_escaped_underscores_in_urls(markdown)
    assert "research_reports" in result
    assert r"research\_reports" not in result
