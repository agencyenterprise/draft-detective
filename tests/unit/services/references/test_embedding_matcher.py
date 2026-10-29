"""Unit tests for ReferenceEmbeddingMatcher: indexing, ranking and failure paths.

The embeddings client is faked with hand-picked vectors so the cosine ranking is
known in advance; no network or model is called.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.references.embedding_matcher import ReferenceEmbeddingMatcher
from lib.workflows.document_summarization.state import FileSummary

MODULE = "lib.services.references.embedding_matcher"

# Three documents along distinct axes; the magnitudes differ on purpose so the
# ranking only comes out right if vectors are normalized before the dot product.
DOC_VECTORS = [[10.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 3.0]]


def _summary(n: int) -> FileSummary:
    return FileSummary(
        file_id=f"file-{n}",
        title=f"Title {n}",
        authors=f"Author {n}",
        publication_date="2020",
        abstract=f"Abstract {n}",
        summary=f"Summary {n}",
    )


SUMMARIES = [_summary(n) for n in range(len(DOC_VECTORS))]


@pytest.fixture
def embeddings() -> Iterator[MagicMock]:
    client = MagicMock()
    client.aembed_documents = AsyncMock()
    limiter = MagicMock()
    limiter.aacquire = AsyncMock()
    with (
        patch(f"{MODULE}.init_embeddings", return_value=client),
        patch(f"{MODULE}.get_rate_limiter", return_value=limiter),
    ):
        yield client


async def _indexed_matcher(embeddings: MagicMock) -> ReferenceEmbeddingMatcher:
    matcher = ReferenceEmbeddingMatcher(openai_api_key="sk-test")
    embeddings.aembed_documents.return_value = DOC_VECTORS
    await matcher.index_summaries(SUMMARIES)
    return matcher


@pytest.mark.asyncio
async def test_index_embeds_citation_shaped_text(embeddings):
    await _indexed_matcher(embeddings)

    texts = embeddings.aembed_documents.await_args.args[0]
    assert texts[0] == (
        "Title: Title 0\nAuthors: Author 0\nYear: 2020\nAbstract: Abstract 0"
    )


@pytest.mark.asyncio
async def test_candidates_are_ranked_by_cosine_similarity(embeddings):
    matcher = await _indexed_matcher(embeddings)
    # By angle the order is doc 1, doc 2, doc 0. Raw dot products (1.0, 0.9, 1.5)
    # would give doc 2, doc 0, doc 1 instead, so this fails without normalization.
    embeddings.aembed_documents.return_value = [[0.1, 0.9, 0.5]]

    [candidates] = await matcher.find_candidates(["a reference"], top_k=3)

    assert [c.doc_index for c in candidates] == [1, 2, 0]
    assert [c.file_id for c in candidates] == ["file-1", "file-2", "file-0"]
    assert candidates[0].summary == SUMMARIES[1]
    scores = [c.similarity_score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] <= 1.0


@pytest.mark.asyncio
async def test_each_reference_gets_its_own_top_k(embeddings):
    matcher = await _indexed_matcher(embeddings)
    embeddings.aembed_documents.return_value = [[0.0, 0.0, 1.0], [1.0, 0.1, 0.0]]

    first, second = await matcher.find_candidates(["ref a", "ref b"], top_k=1)

    assert [c.doc_index for c in first] == [2]
    assert [c.doc_index for c in second] == [0]


@pytest.mark.asyncio
async def test_top_k_is_capped_at_the_number_of_indexed_documents(embeddings):
    matcher = await _indexed_matcher(embeddings)
    embeddings.aembed_documents.return_value = [[1.0, 1.0, 1.0]]

    [candidates] = await matcher.find_candidates(["ref"], top_k=50)

    assert sorted(c.doc_index for c in candidates) == [0, 1, 2]


@pytest.mark.asyncio
async def test_empty_index_returns_one_empty_list_per_reference(embeddings):
    matcher = ReferenceEmbeddingMatcher(openai_api_key="sk-test")
    await matcher.index_summaries([])

    assert await matcher.find_candidates(["a", "b"]) == [[], []]
    embeddings.aembed_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_reindexing_with_no_summaries_clears_previous_index(embeddings):
    matcher = await _indexed_matcher(embeddings)
    await matcher.index_summaries([])

    assert await matcher.find_candidates(["a"]) == [[]]


@pytest.mark.asyncio
async def test_no_reference_texts_skips_embedding(embeddings):
    matcher = await _indexed_matcher(embeddings)
    embeddings.aembed_documents.reset_mock()

    assert await matcher.find_candidates([]) == []
    embeddings.aembed_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_index_error_is_logged_and_reraised(embeddings):
    matcher = ReferenceEmbeddingMatcher(openai_api_key="sk-test")
    embeddings.aembed_documents.side_effect = RuntimeError("rate limited")

    with patch(f"{MODULE}.log_embedding_error") as log_error:
        with pytest.raises(RuntimeError, match="rate limited"):
            await matcher.index_summaries(SUMMARIES)

    assert log_error.call_args.kwargs["caller"].endswith(".index_summaries")


@pytest.mark.asyncio
async def test_find_candidates_error_is_logged_and_reraised(embeddings):
    matcher = await _indexed_matcher(embeddings)
    embeddings.aembed_documents.side_effect = RuntimeError("timeout")

    with patch(f"{MODULE}.log_embedding_error") as log_error:
        with pytest.raises(RuntimeError, match="timeout"):
            await matcher.find_candidates(["ref"])

    assert log_error.call_args.kwargs["caller"].endswith(".find_candidates")


@pytest.mark.asyncio
async def test_error_log_carries_the_run_ids(embeddings):
    matcher = ReferenceEmbeddingMatcher(
        openai_api_key="sk-test", workflow_run_id="run-1", project_id="proj-1"
    )
    embeddings.aembed_documents.side_effect = RuntimeError("rate limited")

    with patch(f"{MODULE}.log_embedding_error") as log_error:
        with pytest.raises(RuntimeError):
            await matcher.index_summaries(SUMMARIES)

    assert log_error.call_args.kwargs["workflow_run_id"] == "run-1"
    assert log_error.call_args.kwargs["project_id"] == "proj-1"
