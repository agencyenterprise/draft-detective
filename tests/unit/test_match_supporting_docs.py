"""Unit tests for reference-to-supporting-document matching."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.agents.document_summarizer import DocumentSummary
from lib.agents.reference_matcher import ReferenceMatchResult
from lib.models.bibliography_item import BibliographyItem
from lib.workflows.reference_extraction.nodes.match_supporting_docs import (
    _format_candidate,
    _match_reference,
    match_supporting_docs_node,
)

# Constant for patch target
MATCHER_AGENT_PATH = "lib.workflows.reference_extraction.nodes.match_supporting_docs.ReferenceMatcherAgent"


def make_summary(title: str, authors: str = "Unknown", year: str = "Unknown"):
    """Create a DocumentSummary for testing."""
    return DocumentSummary(
        title=title,
        authors=authors,
        publication_date=year,
        abstract=f"Abstract for {title}",
        summary=f"Summary of {title}",
    )


def make_file_document(file_name: str):
    """Create a mock FileDocument for testing."""
    doc = MagicMock()
    doc.file_name = file_name
    return doc


@pytest.fixture
def mock_runtime():
    """Create mock runtime with context."""
    runtime = MagicMock()
    runtime.context.openai_api_key = "test-key"
    runtime.context.vector_store = None
    return runtime


@pytest.fixture
def mock_state():
    """Factory fixture to create mock states."""

    def _create(
        texts: list[str],
        summaries: dict[int, DocumentSummary] | None = None,
        supporting_files: list | None = None,
    ):
        state = MagicMock()
        state.extracted_reference_texts = texts
        state.supporting_documents_summaries = summaries
        state.supporting_files = supporting_files
        state.config = None  # Prevent decorator from checking agents_to_run
        return state

    return _create


class TestFormatCandidate:
    def test_formats_summary_with_all_fields(self):
        summary = make_summary("Climate Change", "Smith, J.", "2023")
        result = _format_candidate(1, summary)

        assert "1." in result
        assert "Climate Change" in result
        assert "Smith, J." in result
        assert "2023" in result

    def test_handles_unknown_fields(self):
        summary = make_summary("Some Paper")
        result = _format_candidate(1, summary)

        assert "Some Paper" in result
        assert "Unknown" in result


class TestMatchReference:
    @pytest.mark.asyncio
    async def test_returns_no_match_when_no_summaries(self):
        result = await _match_reference("Some reference", {}, [], MagicMock())
        assert result == (-1, "")

    @pytest.mark.asyncio
    async def test_returns_match_when_found(self):
        summaries = {0: make_summary("Paper A"), 1: make_summary("Paper B")}
        supporting_files = [
            make_file_document("paper_a.pdf"),
            make_file_document("paper_b.pdf"),
        ]

        with patch(MATCHER_AGENT_PATH) as MockAgent:
            MockAgent.return_value.ainvoke = AsyncMock(
                return_value=ReferenceMatchResult(
                    matched_index=2, confidence="high", reasoning="Match"
                )
            )
            result = await _match_reference(
                "Author B. Paper B.", summaries, supporting_files, MagicMock()
            )

        # Should return file_name, not title
        assert result == (2, "paper_b.pdf")

    @pytest.mark.asyncio
    async def test_returns_no_match_when_agent_finds_none(self):
        summaries = {0: make_summary("Paper A")}
        supporting_files = [make_file_document("paper_a.pdf")]

        with patch(MATCHER_AGENT_PATH) as MockAgent:
            MockAgent.return_value.ainvoke = AsyncMock(
                return_value=ReferenceMatchResult(
                    matched_index=-1, confidence="none", reasoning="No match"
                )
            )
            result = await _match_reference(
                "Unrelated", summaries, supporting_files, MagicMock()
            )

        assert result == (-1, "")

    @pytest.mark.asyncio
    async def test_handles_agent_error_gracefully(self):
        summaries = {0: make_summary("Paper A")}
        supporting_files = [make_file_document("paper_a.pdf")]

        with patch(MATCHER_AGENT_PATH) as MockAgent:
            MockAgent.return_value.ainvoke = AsyncMock(side_effect=Exception("Error"))
            result = await _match_reference(
                "Some ref", summaries, supporting_files, MagicMock()
            )

        assert result == (-1, "")


class TestMatchSupportingDocsNode:
    @pytest.mark.asyncio
    async def test_empty_texts_returns_empty_list(self, mock_state, mock_runtime):
        state = mock_state(texts=[])
        result = await match_supporting_docs_node(state, mock_runtime)
        assert result["references"] == []

    @pytest.mark.asyncio
    async def test_no_summaries_returns_unmatched_refs(self, mock_state, mock_runtime):
        state = mock_state(texts=["Smith (2020). Paper."])
        result = await match_supporting_docs_node(state, mock_runtime)

        assert len(result["references"]) == 1
        ref = result["references"][0]
        assert isinstance(ref, BibliographyItem)
        assert ref.has_associated_supporting_document is False
        assert ref.index_of_associated_supporting_document == -1

    @pytest.mark.asyncio
    async def test_matches_refs_to_summaries(self, mock_state, mock_runtime):
        summaries = {0: make_summary("Sea Level Rise", "Johnson, M.", "2023")}
        supporting_files = [make_file_document("sea_level_rise.pdf")]
        state = mock_state(
            texts=["Johnson (2023). Sea Level Rise."],
            summaries=summaries,
            supporting_files=supporting_files,
        )

        with patch(MATCHER_AGENT_PATH) as MockAgent:
            MockAgent.return_value.ainvoke = AsyncMock(
                return_value=ReferenceMatchResult(
                    matched_index=1, confidence="high", reasoning="Match"
                )
            )
            result = await match_supporting_docs_node(state, mock_runtime)

        ref = result["references"][0]
        assert ref.has_associated_supporting_document is True
        assert ref.index_of_associated_supporting_document == 1
        # Should use file_name, not document title
        assert ref.name_of_associated_supporting_document == "sea_level_rise.pdf"

    @pytest.mark.asyncio
    async def test_handles_mixed_matches(self, mock_state, mock_runtime):
        """Some refs match, some don't."""
        summaries = {
            0: make_summary("Paper One", "Smith", "2020"),
            1: make_summary("Paper Two", "Jones", "2021"),
        }
        supporting_files = [
            make_file_document("paper_one.pdf"),
            make_file_document("paper_two.pdf"),
        ]
        state = mock_state(
            texts=["Smith (2020). Paper One.", "Jones (2021). Paper Two.", "Unknown."],
            summaries=summaries,
            supporting_files=supporting_files,
        )

        # Return match for first two, no match for third
        responses = iter(
            [
                ReferenceMatchResult(
                    matched_index=1, confidence="high", reasoning="Match"
                ),
                ReferenceMatchResult(
                    matched_index=2, confidence="high", reasoning="Match"
                ),
                ReferenceMatchResult(
                    matched_index=-1, confidence="none", reasoning="No match"
                ),
            ]
        )

        with patch(MATCHER_AGENT_PATH) as MockAgent:
            MockAgent.return_value.ainvoke = AsyncMock(
                side_effect=lambda *a, **k: next(responses)
            )
            result = await match_supporting_docs_node(state, mock_runtime)

        assert len(result["references"]) == 3
        assert result["references"][0].has_associated_supporting_document is True
        assert result["references"][0].name_of_associated_supporting_document == "paper_one.pdf"
        assert result["references"][1].has_associated_supporting_document is True
        assert result["references"][1].name_of_associated_supporting_document == "paper_two.pdf"
        assert result["references"][2].has_associated_supporting_document is False
