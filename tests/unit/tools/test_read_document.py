"""Unit tests for the read_document tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lib.agents.tools.read_document import (
    _read_content,
    _read_document_async,
    MAX_LINES,
)


class TestReadContent:
    """Tests for the _read_content pure function."""

    def test_read_single_line(self):
        """Test reading a single line (end_line is inclusive)."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 2, 2)

        assert "Lines 2-2 of 3 total lines" in result
        assert "2|Line two" in result
        assert "1|Line one" not in result
        assert "3|Line three" not in result

    def test_read_multiple_lines(self):
        """Test reading multiple lines."""
        content = "Line one\nLine two\nLine three\nLine four\nLine five"
        result = _read_content(content, 2, 4)

        assert "Lines 2-4 of 5 total lines" in result
        assert "2|Line two" in result
        assert "3|Line three" in result
        assert "4|Line four" in result
        assert "1|Line one" not in result
        assert "5|Line five" not in result

    def test_read_entire_document(self):
        """Test reading the entire document."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 1, 3)

        assert "Lines 1-3 of 3 total lines" in result
        assert "1|Line one" in result
        assert "2|Line two" in result
        assert "3|Line three" in result

    def test_read_from_start(self):
        """Test reading from the start of document."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 1, 2)

        assert "Lines 1-2 of 3 total lines" in result
        assert "1|Line one" in result
        assert "2|Line two" in result


class TestReadContentLineIndexing:
    """Tests for 1-indexed line number handling."""

    def test_one_indexed_start_line(self):
        """Test that start_line is 1-indexed."""
        content = "First\nSecond\nThird"
        result = _read_content(content, 1, 1)

        assert "1|First" in result
        assert "2|Second" not in result

    def test_output_line_numbers_are_one_indexed(self):
        """Test that output line numbers are 1-indexed."""
        content = "A\nB\nC\nD\nE"
        result = _read_content(content, 3, 4)

        assert "3|C" in result
        assert "4|D" in result
        # Line 0 should never appear
        assert "0|" not in result


class TestReadContentEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_start_line_beyond_document(self):
        """Test error when start_line exceeds document length."""
        content = "Line one\nLine two"
        result = _read_content(content, 10, 15)

        assert "Error: start_line 10 is beyond document length (2 lines)" in result

    def test_end_line_before_start_line(self):
        """Test error when end_line is before start_line."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 3, 2)

        assert "Error: end_line must be greater than start_line" in result

    def test_end_line_equal_to_start_line_is_valid(self):
        """Test that end_line equal to start_line reads one line."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 2, 2)

        assert "Lines 2-2 of 3 total lines" in result
        assert "2|Line two" in result

    def test_negative_start_line_handled(self):
        """Test that negative start_line is clamped to 0."""
        content = "Line one\nLine two"
        result = _read_content(content, -5, 2)

        assert "Lines 1-2 of 2 total lines" in result
        assert "1|Line one" in result
        assert "2|Line two" in result

    def test_end_line_clamped_to_document_length(self):
        """Test that end_line is clamped to document length."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 1, 100)

        assert "Lines 1-3 of 3 total lines" in result
        assert "3|Line three" in result


class TestReadContentMaxLinesLimit:
    """Tests for MAX_LINES limit behavior."""

    def test_exceeds_max_lines_limit(self):
        """Test error when requested lines exceed MAX_LINES."""
        lines = [f"Line {i}" for i in range(MAX_LINES + 100)]
        content = "\n".join(lines)

        result = _read_content(content, 1, MAX_LINES + 50)

        assert "Error: Requested" in result
        assert f"maximum is {MAX_LINES} lines" in result

    def test_exactly_max_lines(self):
        """Test reading exactly MAX_LINES is allowed."""
        lines = [f"Line {i}" for i in range(MAX_LINES + 10)]
        content = "\n".join(lines)

        result = _read_content(content, 1, MAX_LINES)

        assert "Error:" not in result
        assert f"Lines 1-{MAX_LINES}" in result

    def test_under_max_lines(self):
        """Test reading under MAX_LINES works fine."""
        content = "Line one\nLine two\nLine three"
        result = _read_content(content, 1, 3)

        assert "Error:" not in result
        assert "Lines 1-3" in result


class TestReadContentOutputFormat:
    """Tests for output format and structure."""

    def test_output_header_format(self):
        """Test the header format in output."""
        content = "A\nB\nC\nD\nE"
        result = _read_content(content, 2, 4)

        assert result.startswith("Lines 2-4 of 5 total lines\n\n")

    def test_output_line_format(self):
        """Test the line format with pipe separator."""
        content = "Content here"
        result = _read_content(content, 1, 1)

        assert "1|Content here" in result

    def test_preserves_empty_lines(self):
        """Test that empty lines are preserved in output."""
        content = "Line one\n\nLine three"
        result = _read_content(content, 1, 3)

        assert "1|Line one" in result
        assert "2|" in result  # Empty line preserved
        assert "3|Line three" in result

    def test_preserves_whitespace_in_lines(self):
        """Test that whitespace within lines is preserved."""
        content = "  indented\ttabbed  trailing  "
        result = _read_content(content, 1, 1)

        assert "1|  indented\ttabbed  trailing  " in result


class TestReadDocumentAsync:
    """Tests for the async document read wrapper."""

    @pytest.mark.asyncio
    async def test_returns_error_when_no_main_file(self):
        """Test error message when main file doesn't exist."""
        mock_context = MagicMock()
        mock_context.file_artifacts_service.get_main_file = AsyncMock(return_value=None)

        result = await _read_document_async(1, 10, mock_context)

        assert "Error: Main document not found or has no content" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_no_markdown(self):
        """Test error message when main file has no markdown content."""
        mock_file = MagicMock()
        mock_file.markdown = None

        mock_context = MagicMock()
        mock_context.file_artifacts_service.get_main_file = AsyncMock(
            return_value=mock_file
        )

        result = await _read_document_async(1, 10, mock_context)

        assert "Error: Main document not found or has no content" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_empty_markdown(self):
        """Test error message when main file has empty markdown."""
        mock_file = MagicMock()
        mock_file.markdown = ""

        mock_context = MagicMock()
        mock_context.file_artifacts_service.get_main_file = AsyncMock(
            return_value=mock_file
        )

        result = await _read_document_async(1, 10, mock_context)

        assert "Error: Main document not found or has no content" in result

    @pytest.mark.asyncio
    async def test_handles_service_exception(self):
        """Test graceful handling of service exceptions."""
        mock_context = MagicMock()
        mock_context.file_artifacts_service.get_main_file = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        result = await _read_document_async(1, 10, mock_context)

        assert "Error reading document:" in result
        assert "Database connection failed" in result

    @pytest.mark.asyncio
    async def test_reads_markdown_content(self):
        """Test successful read through markdown content."""
        mock_file = MagicMock()
        mock_file.markdown = "Line one\nLine two\nLine three"

        mock_context = MagicMock()
        mock_context.file_artifacts_service.get_main_file = AsyncMock(
            return_value=mock_file
        )

        result = await _read_document_async(2, 2, mock_context)

        assert "Lines 2-2 of 3 total lines" in result
        assert "2|Line two" in result
