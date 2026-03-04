"""Unit tests for reference-to-supporting-document matching."""

from contextlib import contextmanager
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.agents.batched_reference_matcher import (
    BatchedMatchResult,
    SingleReferenceMatch,
)
from lib.services.reference_embedding_matcher import CandidateMatch
from lib.workflows.document_summarization.state import FileSummary
from lib.workflows.reference_extraction.state import ExtractedReference
from lib.workflows.reference_file_matching.nodes.match_supporting_docs import (
    _resolve_match,
    match_supporting_docs_node,
)
from lib.workflows.reference_file_matching.state import ReferenceFileMatch

EMBEDDING_MATCHER_PATH = "lib.workflows.reference_file_matching.nodes.match_supporting_docs.ReferenceEmbeddingMatcher"
BATCHED_MATCHER_PATH = "lib.workflows.reference_file_matching.nodes.match_supporting_docs.BatchedReferenceMatcherAgent"


def make_summary(
    title: str,
    authors: str = "Unknown",
    year: str = "Unknown",
    file_id: str = "test-file-id",
):
    return FileSummary(
        title=title,
        authors=authors,
        publication_date=year,
        abstract=f"Abstract for {title}",
        summary=f"Summary of {title}",
        file_id=file_id,
    )


def make_candidate(
    doc_index: int,
    summary: FileSummary,
    score: float = 0.9,
    file_id: str | None = None,
):
    return CandidateMatch(
        doc_index=doc_index, similarity_score=score, summary=summary, file_id=file_id
    )


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
    def _create(summaries=None, extracted_refs=None):
        """Create mock runtime with file_artifacts_service that returns summaries."""
        runtime = MagicMock()
        runtime.context.openai_api_key = "test-key"
        runtime.context.vector_store = None

        # Mock file_artifacts_service
        file_artifacts_service = AsyncMock()

        # Map file_ids to summaries
        summaries = summaries or {}

        async def get_summary(file_id):
            # file_ids are like "file-id-0", "file-id-1", extract index
            idx = int(file_id.split("-")[-1])
            return summaries.get(idx)

        file_artifacts_service.get_file_summary = get_summary

        # Mock get_extracted_references
        extracted_refs = extracted_refs or []
        file_artifacts_service.get_extracted_references = AsyncMock(
            return_value=extracted_refs
        )

        runtime.context.file_artifacts_service = file_artifacts_service
        return runtime

    return _create


@pytest.fixture
def mock_state():
    def _create(supporting_file_ids=None, matches=None):
        state = MagicMock()
        state.supporting_file_ids = supporting_file_ids or []
        state.matches = matches or []
        state.config = None
        return state

    return _create


def make_extracted_refs(texts: List[str]) -> List[ExtractedReference]:
    """Create ExtractedReference objects from text strings."""
    return [
        ExtractedReference(id=f"ref-{i}", text=text) for i, text in enumerate(texts)
    ]


class TestResolveMatch:
    """Tests for _resolve_match helper function."""

    def test_returns_no_match_for_none_candidate(self):
        candidates = [make_candidate(0, make_summary("Paper"), file_id="file-id-1")]
        assert _resolve_match("NONE", candidates) is None

    def test_returns_no_match_for_empty_candidates(self):
        assert _resolve_match("A", []) is None

    def test_resolves_letter_to_document(self):
        candidates = [
            make_candidate(0, make_summary("A"), file_id="file-id-a"),
            make_candidate(1, make_summary("B"), file_id="file-id-b"),
        ]

        assert _resolve_match("A", candidates) == "file-id-a"
        assert _resolve_match("B", candidates) == "file-id-b"

    def test_handles_lowercase_letter(self):
        candidates = [make_candidate(0, make_summary("Paper"), file_id="file-id-1")]
        assert _resolve_match("a", candidates) == "file-id-1"

    def test_returns_no_match_for_invalid_letter(self):
        candidates = [make_candidate(0, make_summary("Paper"), file_id="file-id-1")]
        assert _resolve_match("Z", candidates) is None

    def test_resolves_with_none_file_id(self):
        """Test that file_id can be None when candidate doesn't have one."""
        candidates = [make_candidate(0, make_summary("Paper"))]  # No file_id
        assert _resolve_match("A", candidates) is None


class TestTwoStageMatching:
    """Tests for embedding + batched LLM matching."""

    @pytest.mark.asyncio
    async def test_matches_reference_to_document(self, mock_state, mock_runtime):
        summaries = {0: make_summary("Sea Level Rise", "Johnson, M.", "2023")}
        extracted_refs = make_extracted_refs(["Johnson (2023). Sea Level Rise."])
        state = mock_state(supporting_file_ids=["file-id-0"])
        runtime = mock_runtime(summaries=summaries, extracted_refs=extracted_refs)

        with mock_two_stage_matching(
            candidates_per_ref=[[make_candidate(0, summaries[0], file_id="file-id-0")]],
            matches=[make_match(0, "A")],
        ):
            result = await match_supporting_docs_node(state, runtime)

        assert len(result["matches"]) == 1
        match = result["matches"][0]
        assert match.reference_id == "ref-0"
        assert match.file_id == "file-id-0"

    @pytest.mark.asyncio
    async def test_handles_no_match(self, mock_state, mock_runtime):
        summaries = {0: make_summary("Paper 0")}
        extracted_refs = make_extracted_refs(["Unknown reference"])
        state = mock_state(supporting_file_ids=["file-id-0"])
        runtime = mock_runtime(summaries=summaries, extracted_refs=extracted_refs)

        with mock_two_stage_matching(
            candidates_per_ref=[[make_candidate(0, summaries[0], file_id="file-id-0")]],
            matches=[make_match(0, "NONE", "none")],
        ):
            result = await match_supporting_docs_node(state, runtime)

        # No matches when nothing matched
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_handles_mixed_matches(self, mock_state, mock_runtime):
        """Some refs match, some don't."""
        summaries = {
            0: make_summary("Paper One", "Smith", "2020"),
            1: make_summary("Paper Two", "Jones", "2021"),
        }
        extracted_refs = make_extracted_refs(
            ["Smith (2020). Paper One.", "Jones (2021). Paper Two.", "Unknown."]
        )
        state = mock_state(supporting_file_ids=["file-id-0", "file-id-1"])
        runtime = mock_runtime(summaries=summaries, extracted_refs=extracted_refs)

        with mock_two_stage_matching(
            candidates_per_ref=[
                [
                    make_candidate(0, summaries[0], file_id="file-id-0"),
                    make_candidate(1, summaries[1], file_id="file-id-1"),
                ],
                [
                    make_candidate(1, summaries[1], file_id="file-id-1"),
                    make_candidate(0, summaries[0], file_id="file-id-0"),
                ],
                [make_candidate(0, summaries[0], file_id="file-id-0")],
            ],
            matches=[
                make_match(0, "A"),
                make_match(1, "A"),
                make_match(2, "NONE", "none"),
            ],
        ):
            result = await match_supporting_docs_node(state, runtime)

        # Only 2 matches (third ref didn't match)
        assert len(result["matches"]) == 2
        assert result["matches"][0].reference_id == "ref-0"
        assert result["matches"][0].file_id == "file-id-0"
        assert result["matches"][1].reference_id == "ref-1"
        assert result["matches"][1].file_id == "file-id-1"

    @pytest.mark.asyncio
    async def test_handles_batch_error_gracefully(self, mock_state, mock_runtime):
        """Batch matching errors should result in no matches, not exceptions."""
        summaries = {0: make_summary("Paper")}
        extracted_refs = make_extracted_refs(["Some reference"])
        state = mock_state(supporting_file_ids=["file-id-0"])
        runtime = mock_runtime(summaries=summaries, extracted_refs=extracted_refs)

        with mock_two_stage_matching_error(
            candidates_per_ref=[[make_candidate(0, summaries[0], file_id="file-id-0")]],
            error=Exception("API Error"),
        ):
            result = await match_supporting_docs_node(state, runtime)

        # No matches when batch fails
        assert result["matches"] == []


class TestMatchSupportingDocsNode:
    """Tests for the main node entry point."""

    @pytest.mark.asyncio
    async def test_empty_refs(self, mock_state, mock_runtime):
        state = mock_state()
        runtime = mock_runtime(extracted_refs=[])
        result = await match_supporting_docs_node(state, runtime)
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_skips_already_matched_references(self, mock_state, mock_runtime):
        """References already in state.matches must not be re-matched, and their matches must be preserved."""
        summaries = {0: make_summary("Paper B", "Jones", "2021", file_id="file-id-0")}
        extracted_refs = make_extracted_refs(["Already matched ref", "New unmatched ref"])
        existing_match = ReferenceFileMatch(
            reference_id="ref-0", file_id="file-id-0", is_manual=True
        )
        state = mock_state(supporting_file_ids=["file-id-0"], matches=[existing_match])
        runtime = mock_runtime(summaries=summaries, extracted_refs=extracted_refs)

        with mock_two_stage_matching(
            candidates_per_ref=[[make_candidate(0, summaries[0], file_id="file-id-0")]],
            matches=[make_match(0, "A")],
        ):
            result = await match_supporting_docs_node(state, runtime)

        assert len(result["matches"]) == 2
        ref_ids = {m.reference_id for m in result["matches"]}
        assert "ref-0" in ref_ids
        assert "ref-1" in ref_ids
        # Manual match must be preserved unchanged
        manual = next(m for m in result["matches"] if m.reference_id == "ref-0")
        assert manual.is_manual is True
        assert manual.file_id == "file-id-0"

    @pytest.mark.asyncio
    async def test_all_refs_already_matched_skips_matching(
        self, mock_state, mock_runtime
    ):
        """When all references are already matched, the two-stage matching is not invoked."""
        extracted_refs = make_extracted_refs(["Already matched ref"])
        existing_match = ReferenceFileMatch(
            reference_id="ref-0", file_id="file-id-0", is_manual=False
        )
        state = mock_state(supporting_file_ids=["file-id-0"], matches=[existing_match])
        runtime = mock_runtime(extracted_refs=extracted_refs)

        with mock_two_stage_matching(candidates_per_ref=[], matches=[]) as (
            MockEmbed,
            MockBatched,
        ):
            result = await match_supporting_docs_node(state, runtime)

        # Existing match preserved, no new matching run
        assert result["matches"] == [existing_match]
        MockEmbed.return_value.find_candidates.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_summaries(self, mock_state, mock_runtime):
        extracted_refs = make_extracted_refs(["Ref"])
        state = mock_state()
        runtime = mock_runtime(extracted_refs=extracted_refs)
        result = await match_supporting_docs_node(state, runtime)
        # No matches when no supporting files
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_no_supporting_files(self, mock_state, mock_runtime):
        extracted_refs = make_extracted_refs(["Ref"])
        state = mock_state(supporting_file_ids=[])
        runtime = mock_runtime(extracted_refs=extracted_refs)
        result = await match_supporting_docs_node(state, runtime)
        # No matches when no supporting files
        assert result["matches"] == []
