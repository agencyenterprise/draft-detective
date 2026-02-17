"""Unit tests for the search_document tool."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lib.agents.tools.search_document import (
    MAX_CHARS_PER_MATCH,
    MAX_MATCHES,
    search_content,
    search_document,
)

# Path to test data files
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "evals" / "data"


class TestSearchContent:
    """Tests for the search_content pure function."""

    def test_simple_match(self):
        content = "Line one\nLine two\nLine three"
        result = search_content(content, "two")

        assert "Found 1 matches" in result
        assert "2:Line two" in result

    def test_case_insensitive_search(self):
        content = "Hello World\nGoodbye World"
        result = search_content(content, "hello")

        assert "Found 1 matches" in result
        assert "1:Hello World" in result

    def test_no_matches_found(self):
        content = "Line one\nLine two\nLine three"
        result = search_content(content, "nonexistent")

        assert "No matches found for pattern: nonexistent" in result

    def test_invalid_regex_pattern(self):
        content = "Some content"
        result = search_content(content, "[invalid")

        assert "Invalid regex pattern:" in result

    def test_regex_pattern_matching(self):
        content = "error: something failed\nwarning: low memory\nerror: crash"
        result = search_content(content, r"error:.*failed")

        assert "Found 1 matches" in result
        assert "1:error: something failed" in result

    def test_multiple_matches(self):
        content = "apple\nbanana\napple pie\norange\napple cider"
        result = search_content(content, "apple")

        assert "Found 3 matches" in result
        assert "1:apple" in result
        assert "3:apple pie" in result
        assert "5:apple cider" in result

    def test_context_lines_before_and_after(self):
        """Test that context lines are included with proper markers."""
        lines = [f"line {i}" for i in range(10)]
        content = "\n".join(lines)
        result = search_content(content, "line 5")

        # Match line should have ":"
        assert "6:line 5" in result

        # Context lines before should have "-"
        assert "4-line 3" in result
        assert "5-line 4" in result

        # Context lines after should have "-"
        assert "7-line 6" in result
        assert "8-line 7" in result

    def test_context_at_start_of_document(self):
        """Context shouldn't go negative for matches at start."""
        content = "match here\nline 2\nline 3"
        result = search_content(content, "match")

        assert "1:match here" in result
        # Should include context after, but nothing before line 1
        assert "2-line 2" in result
        assert "3-line 3" in result

    def test_context_at_end_of_document(self):
        """Context shouldn't exceed document length for matches at end."""
        content = "line 1\nline 2\nmatch here"
        result = search_content(content, "match")

        assert "3:match here" in result
        # Should include context before, but nothing after line 3
        assert "1-line 1" in result
        assert "2-line 2" in result

    def test_overlapping_context_regions(self):
        """Adjacent matches should have merged context regions."""
        content = "line 1\nmatch A\nline 3\nmatch B\nline 5"
        result = search_content(content, "match")

        assert "Found 2 matches" in result
        # Both matches should be present
        assert "2:match A" in result
        assert "4:match B" in result

    def test_line_truncation(self):
        """Long lines should be truncated."""
        long_line = "x" * (MAX_CHARS_PER_MATCH + 100)
        content = f"short\n{long_line}\nshort again"
        result = search_content(content, "xxx")

        # Line should be truncated with "..."
        assert "..." in result
        # Should not contain the full line
        assert long_line not in result

    def test_empty_content(self):
        result = search_content("", "pattern")
        assert "No matches found" in result

    def test_empty_pattern_matches_all(self):
        """Empty pattern matches all non-empty lines."""
        content = "line 1\nline 2\nline 3"
        result = search_content(content, "")

        assert "Found 3 matches" in result

    def test_special_regex_characters(self):
        """Test searching for literal special characters."""
        content = "price: $100\namount: (50)\npath: file.txt"
        result = search_content(content, r"\$100")

        assert "Found 1 matches" in result
        assert "1:price: $100" in result

    def test_regex_pipe_or_pattern(self):
        """Test regex OR pattern using pipe character."""
        content = "error: connection failed\ninfo: connected\nwarning: low memory\ndebug: verbose"
        result = search_content(content, r"error|warning")

        expected = (
            "Found 2 matches for pattern: error|warning\n"
            "\n"
            "1:error: connection failed\n"
            "2-info: connected\n"
            "3:warning: low memory"
        )
        assert result == expected

    def test_multiline_document(self):
        """Test with realistic multi-line document content."""
        content = """# Introduction

This study examines clinical trials conducted in 2023.
The methodology follows established protocols.

## Methods

The clinical trial was conducted over 12 weeks.
Participants were randomly assigned to groups.

## Results

Results from the clinical trial demonstrate improvement."""

        result = search_content(content, "clinical trial")

        # Matches "clinical trials" and "clinical trial" (3 total)
        assert "Found 3 matches" in result
        assert "clinical trial" in result

    def test_grep_like_separator(self):
        """Test that match blocks are separated by --."""
        lines = [f"line {i}" for i in range(20)]
        lines[5] = "match first"
        lines[15] = "match second"
        content = "\n".join(lines)

        result = search_content(content, "match")

        # Blocks should be separated by --
        assert "--" in result

    def test_reference_section_regex_on_air_force_document(self):
        """Test searching for reference section headers in air-force-ai-generated document."""
        markdown_path = TEST_DATA_DIR / "air-force-ai-generated" / "_main.md"
        content = markdown_path.read_text()

        # This regex matches markdown headings (with optional # prefix) for reference sections
        pattern = r"^\s{0,3}#{0,6}\s*(references|bibliography|works cited|literature cited|sources)\b"
        result = search_content(content, pattern)

        # The document has "# References" at line 581
        assert "Found 1 matches" in result
        assert "# References" in result


class TestSearchContentMaxMatches:
    """Tests for MAX_MATCHES limit behavior."""

    def test_respects_max_matches_limit(self):
        """Test that results are limited to MAX_MATCHES."""
        # Create content with more matches than MAX_MATCHES
        lines = [f"match line {i}" for i in range(MAX_MATCHES + 20)]
        content = "\n".join(lines)

        result = search_content(content, "match")

        assert f"Found {MAX_MATCHES + 20} matches" in result
        assert f"showing first {MAX_MATCHES}" in result

    def test_shows_all_when_under_limit(self):
        """Test that all matches shown when under limit."""
        content = "match 1\nmatch 2\nmatch 3"
        result = search_content(content, "match")

        assert "Found 3 matches for pattern" in result
        assert "showing first" not in result


class TestSearchDocument:
    """Tests for the search_document tool function."""

    FILE_ID = "test-file-id"

    def _create_mock_runtime(self, file=None, side_effect=None):
        """Helper to create a mock ToolRuntime."""
        mock_runtime = MagicMock()
        if side_effect:
            mock_runtime.context.file_artifacts_service.get_file_document = AsyncMock(
                side_effect=side_effect
            )
        else:
            mock_runtime.context.file_artifacts_service.get_file_document = AsyncMock(
                return_value=file
            )
        return mock_runtime

    @pytest.mark.asyncio
    async def test_returns_error_when_file_not_found(self):
        """Test error message when file doesn't exist."""
        mock_runtime = self._create_mock_runtime(file=None)

        result = await search_document.coroutine(self.FILE_ID, "pattern", mock_runtime)

        assert "not found or has no content" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_no_markdown(self):
        """Test error message when file has no markdown content."""
        mock_file = MagicMock()
        mock_file.markdown = None

        mock_runtime = self._create_mock_runtime(file=mock_file)

        result = await search_document.coroutine(self.FILE_ID, "pattern", mock_runtime)

        assert "not found or has no content" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_empty_markdown(self):
        """Test error message when file has empty markdown."""
        mock_file = MagicMock()
        mock_file.markdown = ""

        mock_runtime = self._create_mock_runtime(file=mock_file)

        result = await search_document.coroutine(self.FILE_ID, "pattern", mock_runtime)

        # Empty string is falsy, so treated as no content
        assert "not found or has no content" in result

    @pytest.mark.asyncio
    async def test_searches_markdown_content(self):
        """Test successful search through markdown content."""
        mock_file = MagicMock()
        mock_file.markdown = "Line one\nSearchable content here\nLine three"

        mock_runtime = self._create_mock_runtime(file=mock_file)

        result = await search_document.coroutine(
            self.FILE_ID, "Searchable", mock_runtime
        )

        assert "Found 1 matches" in result
        assert "2:Searchable content here" in result

    @pytest.mark.asyncio
    async def test_handles_service_exception(self):
        """Test graceful handling of service exceptions."""
        mock_runtime = self._create_mock_runtime(
            side_effect=Exception("Database connection failed")
        )

        result = await search_document.coroutine(self.FILE_ID, "pattern", mock_runtime)

        assert "Error searching document:" in result
        assert "Database connection failed" in result
