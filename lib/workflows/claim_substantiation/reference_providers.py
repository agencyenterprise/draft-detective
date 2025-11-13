"""Reference providers for claim verification.

This module implements the Strategy pattern to provide references for claim verification
through different methods (citation-based vs RAG-based).
"""

import asyncio
import logging
from typing import List, Optional, Protocol, Set

from pydantic import BaseModel, Field

from lib.agents.citation_detector import Citation, CitationResponse
from lib.agents.claim_extractor import Claim
from lib.agents.claim_verifier import RetrievedPassageInfo
from lib.agents.formatting_utils import (
    format_cited_references,
    format_retrieved_passages,
)
from lib.agents.reference_extractor import BibliographyItem
from lib.services.file import FileDocument
from lib.services.vector_store import (
    get_collection_id,
    get_file_hash_from_path,
    get_vector_store_service,
)
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)

logger = logging.getLogger(__name__)

# Citation-based reference provider settings
MAX_REFERENCE_CHARACTER_COUNT = 100000  # Max characters from full documents

# RAG reference provider settings
MAX_DISTANCE_THRESHOLD = (
    1  # Max cosine distance for passage relevance (0-1 scale, lower = more similar)
)
MAX_QUERY_LENGTH = 3000  # Max characters in enriched query
MAX_BACKING_ITEM_LENGTH = 600  # Max characters per backing item to include in query


class ReferenceContext(BaseModel):
    """Context containing references for claim verification."""

    cited_references: str = Field(
        description="Formatted references cited in the current chunk"
    )
    cited_references_paragraph: str = Field(
        description="Formatted references from other chunks in the same paragraph"
    )
    retrieved_passages: Optional[List[RetrievedPassageInfo]] = Field(
        default=None, description="Passages retrieved via RAG for this claim"
    )


class ReferenceProvider(Protocol):
    """Strategy for providing reference content to claim verifier."""

    async def get_references_for_claim(
        self,
        state: ClaimSubstantiatorState,
        chunk: DocumentChunk,
        claim: Claim,
        claim_index: int,
    ) -> ReferenceContext:
        """Get references for a claim."""
        ...


class CitationBasedReferenceProvider:
    """Provides references from detected citations in the document."""

    async def get_references_for_claim(
        self,
        state: ClaimSubstantiatorState,
        chunk: DocumentChunk,
        claim: Claim,
        claim_index: int,
    ) -> ReferenceContext:
        """Get references based on detected citations."""
        cited_references = format_cited_references(
            state.references,
            state.supporting_files,
            chunk.citations,
            truncate_at_character_count=MAX_REFERENCE_CHARACTER_COUNT,
        )

        paragraph_chunks_citations_not_in_chunk = _get_paragraph_citations_not_in_chunk(
            state, chunk
        )

        paragraph_other_chunk_citations = CitationResponse(
            citations=paragraph_chunks_citations_not_in_chunk,
            rationale="Citations in the paragraph that are not in the chunk",
        )

        cited_references_paragraph = format_cited_references(
            state.references,
            state.supporting_files,
            paragraph_other_chunk_citations,
            truncate_at_character_count=MAX_REFERENCE_CHARACTER_COUNT,
        )

        return ReferenceContext(
            cited_references=cited_references,
            cited_references_paragraph=cited_references_paragraph,
        )


class RAGReferenceProvider:
    """Provides references via RAG retrieval from vector store."""

    async def get_references_for_claim(
        self,
        state: ClaimSubstantiatorState,
        chunk: DocumentChunk,
        claim: Claim,
        claim_index: int,
    ) -> ReferenceContext:
        """
        Get references via RAG retrieval.

        Retrieves relevant passages from ALL supporting documents and lets the
        claim verifier LLM determine if they support/don't support the claim.
        """
        if not state.supporting_files:
            logger.warning(
                f"No supporting files for RAG retrieval on claim {claim_index}"
            )
            return ReferenceContext(cited_references="", cited_references_paragraph="")

        try:
            query = self._build_enriched_query(chunk, claim)

            # Get the passages for the citations in the chunk
            chunk_citation_supporting_files = self._get_supporting_files_for_citations(
                state.supporting_files,
                state.references,
                chunk.citations.citations if chunk.citations else [],
            )
            chunk_citation_passages = await self._get_passages(
                query, chunk_citation_supporting_files
            )

            logger.info(
                f"Retrieved {len(chunk_citation_passages)} passages for chunk {chunk.chunk_index}, claim {claim_index} "
                f"from {len(chunk_citation_supporting_files)} matched supporting files, using query: '{query}'"
            )

            # Get the passages for the other citations in the paragraph
            all_paragraph_citations = get_all_paragraph_citations(state, chunk)
            paragraph_supportings_files = self._get_supporting_files_for_citations(
                state.supporting_files,
                state.references,
                all_paragraph_citations,
            )
            extra_supporting_files = (
                paragraph_supportings_files - chunk_citation_supporting_files
            )
            paragraph_citations_passages = await self._get_passages(
                query, extra_supporting_files
            )

            logger.info(
                f"Retrieved {len(paragraph_citations_passages)} passages for paragraph from chunk {chunk.chunk_index}, claim {claim_index} "
                f"from {len(extra_supporting_files)} matched supporting files, using query: '{query}'"
            )

            retrieved_passage_info = [
                RetrievedPassageInfo(
                    content=p.content,
                    source_file=p.source_file,
                    cosine_distance=p.cosine_distance,
                    chunk_index=p.chunk_index,
                )
                for p in chunk_citation_passages + paragraph_citations_passages
            ]

            return ReferenceContext(
                cited_references=format_retrieved_passages(chunk_citation_passages),
                cited_references_paragraph=format_retrieved_passages(
                    paragraph_citations_passages
                ),
                retrieved_passages=retrieved_passage_info,
            )

        except Exception as e:
            raise Exception(f"RAG retrieval failed for claim {claim_index}") from e

    async def _get_passages(
        self, query: str, supporting_files: List[FileDocument]
    ) -> List[RetrievedPassageInfo]:
        vector_store = get_vector_store_service()

        retrieval_tasks = [
            vector_store.retrieve_relevant_passages(
                query=query,
                collection_id=get_collection_id(
                    get_file_hash_from_path(file_doc.file_path)
                ),
                top_k=10,
            )
            for file_doc in supporting_files
        ]

        results = await asyncio.gather(*retrieval_tasks)
        all_passages = [passage for passages in results for passage in passages]
        all_passages.sort(key=lambda p: p.cosine_distance, reverse=False)
        return all_passages

    def _build_enriched_query(self, chunk: DocumentChunk, claim: Claim) -> str:
        """
        Build an enriched query by combining the claim with citation and backing context.
        This helps the embedding model match the right document by adding author names
        and key contextual information.
        Handles both regular Claim and ToulminClaim.
        """
        query_parts = [claim.claim]

        if chunk.citations and chunk.citations.citations:
            citation_texts = [c.text for c in chunk.citations.citations]
            query_parts.extend(citation_texts)

        if hasattr(claim, "backing") and claim.backing:
            backing_texts = [
                b for b in claim.backing if len(b) < MAX_BACKING_ITEM_LENGTH
            ]
            query_parts.extend(backing_texts)

        enriched_query = " ".join(query_parts)

        if len(enriched_query) > MAX_QUERY_LENGTH:
            enriched_query = enriched_query[:MAX_QUERY_LENGTH]

        return enriched_query

    def _get_supporting_files_for_citation(
        self,
        supporting_files: List[FileDocument],
        references: List[BibliographyItem],
        citation: Citation,
    ) -> Set[FileDocument]:
        """
        Get the supporting files associated with a citation.

        Args:
            supporting_files: The full list of supporting files.
            references: The full list of references.
            citation: The citation.

        Returns:
            The set of supporting files associated with the citation.
        """

        matched_supporting_files = set()
        bibliography_index = citation.index_of_associated_bibliography
        associated_reference = references[bibliography_index - 1]

        if (
            associated_reference.has_associated_supporting_document
            and associated_reference.index_of_associated_supporting_document > 0
        ):
            supporting_file = supporting_files[
                associated_reference.index_of_associated_supporting_document - 1
            ]
            matched_supporting_files.add(supporting_file)

        return matched_supporting_files

    def _get_supporting_files_for_citations(
        self,
        supporting_files: List[FileDocument],
        references: List[BibliographyItem],
        citations: List[Citation],
    ) -> Set[FileDocument]:
        """
        Get the supporting files associated with a list of citations.

        Args:
            supporting_files: The full list of supporting files.
            references: The full list of references.
            citations: The list of citations.

        Returns:
            The set of supporting files associated with the citations.
        """
        matched_supporting_files = set()
        for citation in citations:
            matched_supporting_files.update(
                self._get_supporting_files_for_citation(
                    supporting_files, references, citation
                )
            )
        return matched_supporting_files


def get_all_paragraph_citations(
    state: ClaimSubstantiatorState, target_chunk: DocumentChunk
) -> List[Citation]:
    """Get all citations from the paragraph that includes the `target_chunk`."""

    all_citations = []
    paragraph_chunks = state.get_paragraph_chunks(target_chunk.paragraph_index)

    for chunk in paragraph_chunks:
        if not chunk.citations or not chunk.citations.citations:
            continue

        all_citations.extend(
            [c for c in chunk.citations.citations if is_bibliographic_citation(c)]
        )

    return all_citations


def is_bibliographic_citation(citation: Citation) -> bool:
    """Check if a citation is a bibliographic citation."""

    return citation.needs_bibliography


def _get_paragraph_citations_not_in_chunk(
    state: ClaimSubstantiatorState, chunk: DocumentChunk
) -> List:
    """Extract citations from paragraph chunks that aren't in current chunk."""

    paragraph_chunks = state.get_paragraph_chunks(chunk.paragraph_index)
    citations_not_in_chunk = []

    for other_chunk in paragraph_chunks:
        if other_chunk == chunk:
            continue
        if not other_chunk.citations or not other_chunk.citations.citations:
            continue

        if not chunk.citations:
            citations_not_in_chunk.extend(other_chunk.citations.citations)
        else:
            for citation in other_chunk.citations.citations:
                if citation not in chunk.citations.citations:
                    citations_not_in_chunk.append(citation)

    return citations_not_in_chunk
