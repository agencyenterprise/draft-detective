"""Unit tests for reference-to-supporting-document matching."""

from contextlib import contextmanager
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.agents.document_summarizer import DocumentSummary
from lib.agents.batched_reference_matcher import (
    BatchedMatchResult,
    SingleReferenceMatch,
)
from lib.services.reference_embedding_matcher import CandidateMatch
from lib.workflows.reference_extraction.nodes.match_supporting_docs import (
    _resolve_match,
    match_supporting_docs_node,
)

EMBEDDING_MATCHER_PATH = "lib.workflows.reference_extraction.nodes.match_supporting_docs.ReferenceEmbeddingMatcher"
BATCHED_MATCHER_PATH = "lib.workflows.reference_extraction.nodes.match_supporting_docs.BatchedReferenceMatcherAgent"


def make_summary(title: str, authors: str = "Unknown", year: str = "Unknown"):
    return DocumentSummary(
        title=title,
        authors=authors,
        publication_date=year,
        abstract=f"Abstract for {title}",
        summary=f"Summary of {title}",
    )


def make_file_document(file_name: str):
    doc = MagicMock()
    doc.file_name = file_name
    return doc


def make_candidate(doc_index: int, summary: DocumentSummary, score: float = 0.9):
    return CandidateMatch(doc_index=doc_index, similarity_score=score, summary=summary)


def make_match(ref_idx: int, candidate: str, confidence: str = "high"):
    return SingleReferenceMatch(
        reference_index=ref_idx,
        matched_candidate=candidate,
        confidence=confidence,
        reasoning=f"{'Match' if candidate != 'NONE' else 'No match'}",
    )


@contextmanager
def mock_two_stage_matching(
    candidates_per_ref: List, matches: List[SingleReferenceMatch]
):
    """Mock both embedding matcher and batched LLM matcher."""
    with (
        patch(EMBEDDING_MATCHER_PATH) as MockEmbed,
        patch(BATCHED_MATCHER_PATH) as MockBatched,
    ):
        embed_instance = MagicMock()
        embed_instance.index_summaries = AsyncMock()
        embed_instance.find_candidates = AsyncMock(return_value=candidates_per_ref)
        MockEmbed.return_value = embed_instance

        MockBatched.return_value.match_batch = AsyncMock(
            return_value=BatchedMatchResult(matches=matches)
        )

        yield MockEmbed, MockBatched


@contextmanager
def mock_two_stage_matching_error(candidates_per_ref: List, error: Exception):
    """Mock embedding matcher success but batched LLM matcher failure."""
    with (
        patch(EMBEDDING_MATCHER_PATH) as MockEmbed,
        patch(BATCHED_MATCHER_PATH) as MockBatched,
    ):
        embed_instance = MagicMock()
        embed_instance.index_summaries = AsyncMock()
        embed_instance.find_candidates = AsyncMock(return_value=candidates_per_ref)
        MockEmbed.return_value = embed_instance

        MockBatched.return_value.match_batch = AsyncMock(side_effect=error)

        yield MockEmbed, MockBatched


@pytest.fixture
def mock_runtime():
    runtime = MagicMock()
    runtime.context.openai_api_key = "test-key"
    runtime.context.vector_store = None
    return runtime


@pytest.fixture
def mock_state():
    def _create(texts, summaries=None, supporting_files=None):
        state = MagicMock()
        state.extracted_reference_texts = texts
        state.supporting_documents_summaries = summaries
        state.supporting_files = supporting_files
        state.config = None
        return state

    return _create


class TestResolveMatch:
    """Tests for _resolve_match helper function."""

    def test_returns_no_match_for_none_candidate(self):
        candidates = [make_candidate(0, make_summary("Paper"))]
        files = [make_file_document("paper.pdf")]
        assert _resolve_match("NONE", candidates, files) == (-1, "")

    def test_returns_no_match_for_empty_candidates(self):
        files = [make_file_document("paper.pdf")]
        assert _resolve_match("A", [], files) == (-1, "")

    def test_resolves_letter_to_document(self):
        candidates = [
            make_candidate(0, make_summary("A")),
            make_candidate(1, make_summary("B")),
        ]
        files = [make_file_document("a.pdf"), make_file_document("b.pdf")]

        assert _resolve_match("A", candidates, files) == (1, "a.pdf")
        assert _resolve_match("B", candidates, files) == (2, "b.pdf")

    def test_handles_lowercase_letter(self):
        candidates = [make_candidate(0, make_summary("Paper"))]
        files = [make_file_document("paper.pdf")]
        assert _resolve_match("a", candidates, files) == (1, "paper.pdf")

    def test_returns_no_match_for_invalid_letter(self):
        candidates = [make_candidate(0, make_summary("Paper"))]
        files = [make_file_document("paper.pdf")]
        assert _resolve_match("Z", candidates, files) == (-1, "")


class TestTwoStageMatching:
    """Tests for embedding + batched LLM matching."""

    @pytest.mark.asyncio
    async def test_matches_reference_to_document(self, mock_state, mock_runtime):
        summaries = {0: make_summary("Sea Level Rise", "Johnson, M.", "2023")}
        files = [make_file_document("sea_level_rise.pdf")]
        state = mock_state(
            texts=["Johnson (2023). Sea Level Rise."],
            summaries=summaries,
            supporting_files=files,
        )

        with mock_two_stage_matching(
            candidates_per_ref=[[make_candidate(0, summaries[0])]],
            matches=[make_match(0, "A")],
        ):
            result = await match_supporting_docs_node(state, mock_runtime)

        ref = result["references"][0]
        assert ref.has_associated_supporting_document is True
        assert ref.index_of_associated_supporting_document == 1
        assert ref.name_of_associated_supporting_document == "sea_level_rise.pdf"

    @pytest.mark.asyncio
    async def test_handles_no_match(self, mock_state, mock_runtime):
        summaries = {0: make_summary("Paper 0")}
        files = [make_file_document("paper_0.pdf")]
        state = mock_state(
            texts=["Unknown reference"], summaries=summaries, supporting_files=files
        )

        with mock_two_stage_matching(
            candidates_per_ref=[[make_candidate(0, summaries[0])]],
            matches=[make_match(0, "NONE", "none")],
        ):
            result = await match_supporting_docs_node(state, mock_runtime)

        assert result["references"][0].has_associated_supporting_document is False

    @pytest.mark.asyncio
    async def test_handles_mixed_matches(self, mock_state, mock_runtime):
        """Some refs match, some don't."""
        summaries = {
            0: make_summary("Paper One", "Smith", "2020"),
            1: make_summary("Paper Two", "Jones", "2021"),
        }
        files = [
            make_file_document("paper_one.pdf"),
            make_file_document("paper_two.pdf"),
        ]
        state = mock_state(
            texts=["Smith (2020). Paper One.", "Jones (2021). Paper Two.", "Unknown."],
            summaries=summaries,
            supporting_files=files,
        )

        with mock_two_stage_matching(
            candidates_per_ref=[
                [make_candidate(0, summaries[0]), make_candidate(1, summaries[1])],
                [make_candidate(1, summaries[1]), make_candidate(0, summaries[0])],
                [make_candidate(0, summaries[0])],
            ],
            matches=[
                make_match(0, "A"),
                make_match(1, "A"),
                make_match(2, "NONE", "none"),
            ],
        ):
            result = await match_supporting_docs_node(state, mock_runtime)

        assert len(result["references"]) == 3
        assert result["references"][0].has_associated_supporting_document is True
        assert (
            result["references"][0].name_of_associated_supporting_document
            == "paper_one.pdf"
        )
        assert result["references"][1].has_associated_supporting_document is True
        assert (
            result["references"][1].name_of_associated_supporting_document
            == "paper_two.pdf"
        )
        assert result["references"][2].has_associated_supporting_document is False

    @pytest.mark.asyncio
    async def test_handles_batch_error_gracefully(self, mock_state, mock_runtime):
        """Batch matching errors should result in no matches, not exceptions."""
        summaries = {0: make_summary("Paper")}
        files = [make_file_document("paper.pdf")]
        state = mock_state(
            texts=["Some reference"], summaries=summaries, supporting_files=files
        )

        with mock_two_stage_matching_error(
            candidates_per_ref=[[make_candidate(0, summaries[0])]],
            error=Exception("API Error"),
        ):
            result = await match_supporting_docs_node(state, mock_runtime)

        assert len(result["references"]) == 1
        assert result["references"][0].has_associated_supporting_document is False


class TestMatchSupportingDocsNode:
    """Tests for the main node entry point."""

    @pytest.mark.asyncio
    async def test_empty_texts(self, mock_state, mock_runtime):
        result = await match_supporting_docs_node(mock_state(texts=[]), mock_runtime)
        assert result["references"] == []

    @pytest.mark.asyncio
    async def test_no_summaries(self, mock_state, mock_runtime):
        result = await match_supporting_docs_node(
            mock_state(texts=["Ref"]), mock_runtime
        )
        ref = result["references"][0]
        assert ref.has_associated_supporting_document is False
        assert ref.index_of_associated_supporting_document == -1

    @pytest.mark.asyncio
    async def test_no_supporting_files(self, mock_state, mock_runtime):
        summaries = {0: make_summary("Paper")}
        result = await match_supporting_docs_node(
            mock_state(texts=["Ref"], summaries=summaries, supporting_files=[]),
            mock_runtime,
        )
        ref = result["references"][0]
        assert ref.has_associated_supporting_document is False
