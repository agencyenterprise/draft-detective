"""In-memory embedding-based reference matcher for fast candidate retrieval.

Uses NumPy for cosine similarity search - suitable for up to ~1000 document summaries.
For larger scale, consider migrating to pgvector.
"""

import logging
from typing import Dict, List

import numpy as np
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel

from lib.agents.document_summarizer import DocumentSummary

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_TOP_K = 15


class CandidateMatch(BaseModel):
    """A candidate document match for a reference."""

    doc_index: int
    similarity_score: float
    summary: DocumentSummary


def _normalize(embeddings: np.ndarray) -> np.ndarray:
    """L2 normalize embeddings for cosine similarity via dot product."""
    return embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)


def _format_summary(summary: DocumentSummary) -> str:
    """Title/Authors/Year/Abstract order mirrors typical citation structure,
    improving semantic similarity with reference text."""
    return (
        f"Title: {summary.title}\n"
        f"Authors: {summary.authors}\n"
        f"Year: {summary.publication_date}\n"
        f"Abstract: {summary.abstract}"
    )


class ReferenceEmbeddingMatcher:
    """In-memory embedding index for fast reference-to-document matching.

    Why two-stage: Direct LLM matching doesn't scale beyond ~20 docs due to
    context limits and cost. Embeddings pre-filter to top-K candidates,
    reducing LLM calls while maintaining accuracy.
    """

    def __init__(self, openai_api_key: str):
        self._embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL, api_key=openai_api_key
        )
        self._doc_embeddings_normalized: np.ndarray | None = None
        self._doc_indices: List[int] = []
        self._summaries: Dict[int, DocumentSummary] = {}

    async def index_summaries(self, summaries: Dict[int, DocumentSummary]) -> None:
        """Pre-index at workflow start to avoid re-embedding on each lookup."""
        if not summaries:
            logger.warning("No summaries to index")
            self._doc_embeddings_normalized = None
            self._doc_indices = []
            self._summaries = {}
            return

        self._summaries = summaries
        self._doc_indices = list(summaries.keys())

        texts = [_format_summary(summaries[idx]) for idx in self._doc_indices]
        logger.info(f"Embedding {len(texts)} document summaries")

        vectors = await self._embeddings.aembed_documents(texts)
        # We need to pre-normalize during indexing to avoid repeated computation
        self._doc_embeddings_normalized = _normalize(np.array(vectors))

        logger.info(
            f"Indexed {len(self._doc_indices)} document summaries "
            f"(embedding dim: {self._doc_embeddings_normalized.shape[1]})"
        )

    async def find_candidates(
        self,
        reference_texts: List[str],
        top_k: int = DEFAULT_TOP_K,
    ) -> List[List[CandidateMatch]]:
        """Batch-embed references and find top-K similar docs via cosine similarity."""
        if self._doc_embeddings_normalized is None or not self._doc_indices:
            logger.warning("No documents indexed, returning empty candidates")
            return [[] for _ in reference_texts]

        if not reference_texts:
            return []

        logger.info(f"Embedding {len(reference_texts)} reference texts")
        ref_vectors = await self._embeddings.aembed_documents(reference_texts)
        ref_normalized = _normalize(np.array(ref_vectors))

        # We need to compute cosine similarity via dot product of normalized vectors: (num_refs, num_docs) to return the correct similarity scores
        similarities = ref_normalized @ self._doc_embeddings_normalized.T

        effective_k = min(top_k, len(self._doc_indices))

        results: List[List[CandidateMatch]] = []
        for ref_similarities in similarities:
            top_indices = np.argsort(ref_similarities)[-effective_k:][::-1]
            candidates = [
                CandidateMatch(
                    doc_index=self._doc_indices[idx],
                    similarity_score=float(ref_similarities[idx]),
                    summary=self._summaries[self._doc_indices[idx]],
                )
                for idx in top_indices
            ]
            results.append(candidates)

        logger.info(
            f"Found candidates for {len(reference_texts)} references "
            f"(top-{effective_k} each)"
        )

        return results

    def get_indexed_count(self) -> int:
        return len(self._doc_indices)
