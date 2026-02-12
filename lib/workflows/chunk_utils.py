import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple, cast

from lib.agents.citation_detector import CitationResponse
from lib.agents.claim_categorizer import ClaimCategorizationResponseWithClaimIndex
from lib.agents.claim_extractor import ClaimResponseWithChunkIndex
from lib.agents.models import ChunkWithIndex
from lib.workflows.chunk_splitting.state import ChunkSplittingState
from lib.workflows.citation_detection.state import CitationDetectionState
from lib.workflows.claim_extraction.state import ClaimExtractionState
from lib.workflows.claim_extraction_v2.state import ClaimExtractionV2State
from lib.workflows.models import WorkflowRunType
from lib.workflows.util import get_state_by_type

if TYPE_CHECKING:
    from lib.workflows.types import WorkflowState

logger = logging.getLogger(__name__)


class AnalyzedChunk(ChunkWithIndex):
    """Enriched document chunk with all claim analysis results.

    Extends the base ChunkWithIndex with claim extraction, citation detection,
    categorization, substantiation, and inference validation results.
    """

    claims: Optional[ClaimResponseWithChunkIndex] = None
    citations: Optional[CitationResponse] = None
    claim_categories: List[ClaimCategorizationResponseWithClaimIndex] = []


def _resolve_claim_state(
    existing_states: List["WorkflowState"],
) -> Tuple[
    List[ClaimResponseWithChunkIndex],
    List[ClaimCategorizationResponseWithClaimIndex],
]:
    """Resolve claims and categories from existing states.

    Prefers v2 claim extraction state when present, falls back to v1.
    V2 has no categories (always empty list).
    """
    # Try v2 first
    v2_state_raw = get_state_by_type(
        WorkflowRunType.CLAIM_EXTRACTION_V2, existing_states
    )
    if v2_state_raw is not None:
        v2_state = cast(ClaimExtractionV2State, v2_state_raw)
        logger.info("Using claim extraction v2 state for chunk enrichment")
        return v2_state.claims, v2_state.claim_categories

    # Fall back to v1
    v1_state_raw = get_state_by_type(
        WorkflowRunType.CLAIM_EXTRACTION, existing_states
    )
    if v1_state_raw is not None:
        v1_state = cast(ClaimExtractionState, v1_state_raw)
        return v1_state.claims, v1_state.claim_categories

    return [], []


def build_analyzed_chunks(
    existing_states: List["WorkflowState"],
) -> List[AnalyzedChunk]:
    """Build AnalyzedChunk objects from existing workflow states.

    This function extracts chunks from chunk splitting state and enriches them
    with claims, claim categories, and citations from their respective workflow states.
    Prefers v2 claim extraction state when present, falls back to v1.
    If neither is present, claim fields will not be populated.

    Args:
        existing_states: List of workflow states from dependency workflows

    Returns:
        List of AnalyzedChunk objects with all available analysis results.
        Returns empty list if chunk splitting state is not found.
    """
    # Get chunks from chunk splitting workflow
    chunk_splitting_state_raw = get_state_by_type(
        WorkflowRunType.CHUNK_SPLITTING, existing_states
    )
    if chunk_splitting_state_raw is None:
        return []

    chunk_splitting_state = cast(ChunkSplittingState, chunk_splitting_state_raw)

    # Resolve claims and categories (v2 preferred, v1 fallback)
    claims_list, categories_list = _resolve_claim_state(existing_states)

    # Get citation detection results from citation detection workflow (optional)
    citation_detection_state_raw = get_state_by_type(
        WorkflowRunType.CITATION_DETECTION, existing_states
    )
    citation_detection_state = (
        cast(CitationDetectionState, citation_detection_state_raw)
        if citation_detection_state_raw is not None
        else None
    )

    # Build maps for efficient lookup
    claims_by_chunk_index: Dict[int, ClaimResponseWithChunkIndex] = {}
    for claim_response in claims_list:
        chunk_index = claim_response.chunk_index
        if chunk_index not in claims_by_chunk_index:
            claims_by_chunk_index[chunk_index] = claim_response

    categories_by_chunk_and_claim: Dict[
        Tuple[int, int], List[ClaimCategorizationResponseWithClaimIndex]
    ] = {}
    for category in categories_list:
        key = (category.chunk_index, category.claim_index)
        if key not in categories_by_chunk_and_claim:
            categories_by_chunk_and_claim[key] = []
        categories_by_chunk_and_claim[key].append(category)

    # Build map of citations by chunk index from citation detection state (optional)
    citations_by_chunk_index: Dict[int, CitationResponse] = {}
    if citation_detection_state is not None:
        for citation_response_with_index in citation_detection_state.citations:
            citations_by_chunk_index[citation_response_with_index.chunk_index] = (
                citation_response_with_index
            )

    # Convert base chunks to AnalyzedChunk and populate with claims, categories, and citations
    chunks = []
    for doc_chunk in chunk_splitting_state.chunks:
        analyzed_chunk = AnalyzedChunk(
            content=doc_chunk.content,
            chunk_index=doc_chunk.chunk_index,
            paragraph_index=doc_chunk.paragraph_index,
            headings=doc_chunk.headings,
            start_line=doc_chunk.start_line,
            end_line=doc_chunk.end_line,
        )

        # Add claims if available
        if doc_chunk.chunk_index in claims_by_chunk_index:
            analyzed_chunk.claims = claims_by_chunk_index[doc_chunk.chunk_index]

        # Add claim categories if available
        claim_categories = []
        if analyzed_chunk.claims and analyzed_chunk.claims.claims:
            for claim_index in range(len(analyzed_chunk.claims.claims)):
                key = (doc_chunk.chunk_index, claim_index)
                if key in categories_by_chunk_and_claim:
                    claim_categories.extend(categories_by_chunk_and_claim[key])
        analyzed_chunk.claim_categories = claim_categories

        # Add citations from citation detection workflow if available
        if doc_chunk.chunk_index in citations_by_chunk_index:
            analyzed_chunk.citations = citations_by_chunk_index[doc_chunk.chunk_index]

        chunks.append(analyzed_chunk)

    return chunks


def find_chunk_index_by_text(
    chunks: Sequence[ChunkWithIndex], text: str
) -> Optional[int]:
    """Find the chunk index of the first chunk that contains the given text."""

    for chunk in chunks:
        if text in chunk.content:
            return chunk.chunk_index

    return None


def find_chunk_by_index(
    chunks: List[AnalyzedChunk], chunk_index: int
) -> Optional[AnalyzedChunk]:
    """Find a chunk by its index."""
    for chunk in chunks:
        if chunk.chunk_index == chunk_index:
            return chunk
    return None
