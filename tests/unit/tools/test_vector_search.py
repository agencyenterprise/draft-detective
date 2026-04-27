"""Unit tests for the vector_search tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.agents.tools.vector_search import format_passages_with_lines, vector_search
from lib.services.vector_store import RetrievedPassage


def _passage(
    content: str,
    source_file: str,
    start_line: int,
    end_line: int | None = None,
) -> RetrievedPassage:
    """Helper to create a RetrievedPassage with a default cosine_distance."""
    return RetrievedPassage(
        content=content,
        source_file=source_file,
        start_line=start_line,
        end_line=end_line if end_line is not None else start_line,
        cosine_distance=0.1,
    )


class TestFormatPassagesWithLines:
    """Tests for the format_passages_with_lines pure function."""

    def test_single_passage(self):
        """Test formatting a single passage with context lines."""
        content = "line 0\nline 1\nline 2\nmatch line\nline 4\nline 5\nline 6"
        passages = [_passage("match line", "doc.pdf", start_line=4)]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        assert "Showing 1 most similar passages in 'doc.pdf'" in result
        assert "4:match line" in result
        # Context lines before
        assert "2-line 1" in result
        assert "3-line 2" in result
        # Context lines after
        assert "5-line 4" in result
        assert "6-line 5" in result

    def test_multiple_passages_separated(self):
        """Test that non-contiguous passages are separated by --."""
        lines = [f"line {i}" for i in range(20)]
        content = "\n".join(lines)
        passages = [
            _passage("line 3", "doc.pdf", start_line=4),
            _passage("line 15", "doc.pdf", start_line=16),
        ]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        assert "Showing 2 most similar passages in 'doc.pdf'" in result
        assert "4:line 3" in result
        assert "16:line 15" in result
        assert "\n--\n" in result

    def test_adjacent_passages_merged(self):
        """Test that adjacent passages have their context merged."""
        lines = [f"line {i}" for i in range(10)]
        content = "\n".join(lines)
        # Two passages close enough that their context windows overlap
        passages = [
            _passage("line 3", "doc.pdf", start_line=4),
            _passage("line 5", "doc.pdf", start_line=6),
        ]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        # Should be a single merged block (no -- separator)
        blocks = result.split("\n--\n")
        # Header is part of the first block, so only 1 block total
        assert len(blocks) == 1
        assert "4:line 3" in result
        assert "6:line 5" in result

    def test_passage_at_start_of_document(self):
        """Context shouldn't go negative for passages at start."""
        content = "match here\nline 1\nline 2\nline 3\nline 4"
        passages = [_passage("match here", "doc.pdf", start_line=1)]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        assert "1:match here" in result
        assert "2-line 1" in result
        assert "3-line 2" in result
        # No negative line numbers
        assert "0-" not in result
        assert "-1-" not in result

    def test_passage_at_end_of_document(self):
        """Context shouldn't exceed document length for passages at end."""
        content = "line 0\nline 1\nline 2\nmatch here"
        passages = [_passage("match here", "doc.pdf", start_line=4)]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        assert "4:match here" in result
        # Context before
        assert "3-line 2" in result

    def test_matched_lines_use_colon_separator(self):
        """Matched lines should use : and context lines should use -."""
        content = "ctx before\nmatch\nctx after"
        passages = [_passage("match", "doc.pdf", start_line=2)]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        assert "2:match" in result
        assert "1-ctx before" in result
        assert "3-ctx after" in result

    def test_empty_passages_list(self):
        """Test formatting with no passages produces header only."""
        content = "some content"
        result = format_passages_with_lines([], content, "doc.pdf")

        assert "Showing 0 most similar passages in 'doc.pdf'" in result

    def test_preserves_empty_lines_in_content(self):
        """Test that empty lines in the document are preserved."""
        content = "line 1\n\nmatch here\n\nline 5"
        passages = [_passage("match here", "doc.pdf", start_line=3)]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        assert "3:match here" in result
        assert "2-" in result  # Empty line preserved

    def test_header_format(self):
        """Test the header format includes file name and count."""
        content = "line 1\nline 2\nline 3"
        passages = [_passage("line 2", "report.pdf", start_line=2)]

        result = format_passages_with_lines(passages, content, "report.pdf")

        assert result.startswith("Showing 1 most similar passages in 'report.pdf'\n\n")

    def test_multiline_document_with_multiple_blocks(self):
        """Test realistic multi-line document with passages from different sections."""
        lines = [
            "# Introduction",  # line 1
            "",  # line 2
            "This study examines clinical trials conducted in 2023.",  # line 3
            "The methodology follows established protocols.",  # line 4
            "",  # line 5
            "## Methods",  # line 6
            "",  # line 7
            "The clinical trial was conducted over 12 weeks.",  # line 8
            "Participants were randomly assigned to groups.",  # line 9
            "",  # line 10
            "## Results",  # line 11
            "",  # line 12
            "The outcomes were measured using standard metrics.",  # line 13
            "Statistical analysis was performed on all data.",  # line 14
            "Confidence intervals were calculated for each group.",  # line 15
            "Results from the clinical trial demonstrate improvement.",  # line 16
            "Further studies are recommended.",  # line 17
        ]
        content = "\n".join(lines)

        passages = [
            _passage(
                "The clinical trial was conducted over 12 weeks.",
                "study.pdf",
                start_line=8,
            ),
            _passage(
                "Results from the clinical trial demonstrate improvement.",
                "study.pdf",
                start_line=16,
            ),
        ]

        result = format_passages_with_lines(passages, content, "study.pdf")

        assert "Showing 2 most similar passages in 'study.pdf'" in result
        assert "8:The clinical trial was conducted over 12 weeks." in result
        assert "16:Results from the clinical trial demonstrate improvement." in result
        assert "\n--\n" in result

    def test_multiline_chunk_all_lines_matched(self):
        """Test that a multi-line chunk marks all its lines with : separator."""
        lines = [f"line {i}" for i in range(10)]
        content = "\n".join(lines)
        # A chunk spanning lines 4-6 (1-indexed)
        passages = [
            _passage("line 3\nline 4\nline 5", "doc.pdf", start_line=4, end_line=6)
        ]

        result = format_passages_with_lines(passages, content, "doc.pdf")

        # All chunk lines should be marked with :
        assert "4:line 3" in result
        assert "5:line 4" in result
        assert "6:line 5" in result
        # Context lines before and after should use -
        assert "2-line 1" in result
        assert "3-line 2" in result
        assert "7-line 6" in result
        assert "8-line 7" in result


class TestVectorSearch:
    """Tests for the vector_search tool function."""

    FILE_ID = "test-file-id"

    def _create_mock_runtime(
        self,
        supporting_files=None,
        vector_store=None,
        side_effect=None,
    ):
        """Helper to create a mock ToolRuntime."""
        mock_runtime = MagicMock()

        if side_effect:
            mock_runtime.context.file_artifacts_service.get_supporting_files = (
                AsyncMock(side_effect=side_effect)
            )
        else:
            mock_runtime.context.file_artifacts_service.get_supporting_files = (
                AsyncMock(return_value=supporting_files or [])
            )

        mock_runtime.context.vector_store = vector_store
        return mock_runtime

    def _create_mock_file(
        self,
        file_id="test-file-id",
        file_name="doc.pdf",
        markdown="content",
        file_path="/files/abc123",
    ):
        """Helper to create a mock supporting file."""
        mock_file = MagicMock()
        mock_file.file_id = file_id
        mock_file.file_name = file_name
        mock_file.markdown = markdown
        mock_file.file_path = file_path
        return mock_file

    @pytest.mark.asyncio
    @pytest.mark.parametrize("top_k", [0, -1, -100, 51, 100])
    async def test_returns_error_when_top_k_out_of_range(self, top_k: int):
        """Test error message when top_k is outside the allowed 1-50 range."""
        mock_runtime = self._create_mock_runtime()

        result = await vector_search.coroutine(  # type: ignore[attr-defined]
            self.FILE_ID, "query", top_k, mock_runtime
        )

        assert result == "Error: top_k must be between 1 and 50."

    @pytest.mark.asyncio
    @pytest.mark.parametrize("top_k", [1, 25, 50])
    async def test_accepts_valid_top_k_values(self, top_k: int):
        """Test that valid top_k values (1-50) are accepted and don't trigger the guard."""
        mock_vector_store = MagicMock()
        mock_runtime = self._create_mock_runtime(vector_store=mock_vector_store)

        result = await vector_search.coroutine(  # type: ignore[attr-defined]
            self.FILE_ID, "query", top_k, mock_runtime
        )

        # Should pass the guard and hit the "no file found" error instead
        assert "top_k must be between" not in result

    @pytest.mark.asyncio
    async def test_returns_error_when_vector_store_unavailable(self):
        """Test error message when vector store is not available."""
        mock_runtime = self._create_mock_runtime(vector_store=None)

        result = await vector_search.coroutine(self.FILE_ID, "query", 10, mock_runtime)

        assert "Vector store is not available" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_file_not_found(self):
        """Test error message when file_id doesn't match any supporting file."""
        mock_vector_store = MagicMock()
        mock_file = self._create_mock_file(file_id="other-file-id")
        mock_runtime = self._create_mock_runtime(
            supporting_files=[mock_file],
            vector_store=mock_vector_store,
        )

        result = await vector_search.coroutine(self.FILE_ID, "query", 10, mock_runtime)

        assert f"No supporting file found with file_id '{self.FILE_ID}'" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_no_supporting_files(self):
        """Test error message when there are no supporting files."""
        mock_vector_store = MagicMock()
        mock_runtime = self._create_mock_runtime(
            supporting_files=[],
            vector_store=mock_vector_store,
        )

        result = await vector_search.coroutine(self.FILE_ID, "query", 10, mock_runtime)

        assert "No supporting file found" in result

    @pytest.mark.asyncio
    async def test_returns_no_passages_message(self):
        """Test message when search returns no relevant passages."""
        mock_file = self._create_mock_file()
        mock_vector_store = AsyncMock()
        mock_vector_store.ensure_collection_indexed = AsyncMock()
        mock_vector_store.retrieve_relevant_passages = AsyncMock(return_value=[])

        mock_runtime = self._create_mock_runtime(
            supporting_files=[mock_file],
            vector_store=mock_vector_store,
        )

        with (
            patch(
                "lib.agents.tools.vector_search.get_file_hash_from_path",
                return_value="hash123",
            ),
            patch(
                "lib.agents.tools.vector_search.get_collection_id",
                return_value="col_123",
            ),
        ):
            result = await vector_search.coroutine(
                self.FILE_ID, "query", 10, mock_runtime
            )

        assert "No relevant passages found in 'doc.pdf'" in result

    @pytest.mark.asyncio
    async def test_successful_search_returns_formatted_passages(self):
        """Test successful search returns formatted passage output."""
        markdown = "line 0\nline 1\nline 2\nmatch line\nline 4\nline 5\nline 6"
        mock_file = self._create_mock_file(markdown=markdown)
        passages = [
            _passage("match line", "doc.pdf", start_line=4),
        ]

        mock_vector_store = AsyncMock()
        mock_vector_store.ensure_collection_indexed = AsyncMock()
        mock_vector_store.retrieve_relevant_passages = AsyncMock(return_value=passages)

        mock_runtime = self._create_mock_runtime(
            supporting_files=[mock_file],
            vector_store=mock_vector_store,
        )

        with (
            patch(
                "lib.agents.tools.vector_search.get_file_hash_from_path",
                return_value="hash123",
            ),
            patch(
                "lib.agents.tools.vector_search.get_collection_id",
                return_value="col_123",
            ),
        ):
            result = await vector_search.coroutine(
                self.FILE_ID, "query", 10, mock_runtime
            )

        assert "Showing 1 most similar passages in 'doc.pdf'" in result
        assert "4:match line" in result

    @pytest.mark.asyncio
    async def test_ensures_collection_indexed_before_search(self):
        """Test that ensure_collection_indexed is called before search."""
        markdown = "some content"
        mock_file = self._create_mock_file(markdown=markdown)

        mock_vector_store = AsyncMock()
        mock_vector_store.ensure_collection_indexed = AsyncMock()
        mock_vector_store.retrieve_relevant_passages = AsyncMock(return_value=[])

        mock_runtime = self._create_mock_runtime(
            supporting_files=[mock_file],
            vector_store=mock_vector_store,
        )

        with (
            patch(
                "lib.agents.tools.vector_search.get_file_hash_from_path",
                return_value="hash123",
            ),
            patch(
                "lib.agents.tools.vector_search.get_collection_id",
                return_value="col_123",
            ),
        ):
            await vector_search.coroutine(self.FILE_ID, "query", 5, mock_runtime)

        mock_vector_store.ensure_collection_indexed.assert_called_once_with(
            collection_id="col_123",
            markdown_content=markdown,
            file_name="doc.pdf",
        )
        mock_vector_store.retrieve_relevant_passages.assert_called_once_with(
            query="query", collection_id="col_123", top_k=5
        )

    @pytest.mark.asyncio
    async def test_handles_service_exception(self):
        """Test graceful handling of exceptions during search."""
        mock_runtime = self._create_mock_runtime(
            side_effect=Exception("Connection failed")
        )
        mock_runtime.context.vector_store = MagicMock()

        result = await vector_search.coroutine(self.FILE_ID, "query", 10, mock_runtime)

        assert "Error during vector search:" in result
        assert "Connection failed" in result
