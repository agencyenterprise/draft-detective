import logging

from langgraph.runtime import Runtime

from lib.agents.claim_verifier import (
    ClaimSubstantiationResultWithClaimIndex,
    ClaimVerifierAgent,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.reference_providers import (
    CitationBasedReferenceProvider,
    RAGReferenceProvider,
    ReferenceProvider,
    get_all_paragraph_citations,
)
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.decorators import (
    handle_chunk_errors,
    register_node,
)

logger = logging.getLogger(__name__)


def _needs_substantiation(
    state: ClaimSubstantiatorState, chunk: DocumentChunk, claim_index: int
) -> bool:
    """
    Check if a claim needs substantiation.

    A claim needs substantiation if:
    1. It has citations in the chunk that need to be verified OR in the paragraph that includes the chunk; AND
    2. It needs external verification (or if categorization didn't happen, consider all claims need external verification)
    """

    paragraph_citations = get_all_paragraph_citations(state, chunk)
    if len(paragraph_citations) == 0:
        # If there's no citations in the paragraph, skip verification since there's no document to verify against
        return False

    claim_category = next(
        (c for c in chunk.claim_categories if c.claim_index == claim_index),
        None,
    )

    if not claim_category:
        # In case categorization didn't happen, force verification (consider all claims need external verification)
        return True

    # If the claim needs external verification, verify it
    return claim_category.needs_external_verification


async def _verify_chunk_claims_with_provider(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    reference_provider: ReferenceProvider,
    claim_verifier_agent: ClaimVerifierAgent,
) -> DocumentChunk:
    """Verify chunk claims using the provided reference provider.

    Skips chunks with no claims. For each claim:
    - ALWAYS verifies if the chunk has citations (even if common knowledge)
    - Verifies if the claim needs substantiation (not common knowledge)

    This ensures all citations are validated regardless of common knowledge status.
    """
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(f"Chunk {chunk.chunk_index} has no claims")
        return chunk

    substantiations = []

    for claim_index, claim in enumerate(chunk.claims.claims):
        if not _needs_substantiation(state, chunk, claim_index):
            logger.debug(
                f"Chunk {chunk.chunk_index} claim {claim_index} does not need external verification, skipping verification"
            )
            continue

        ref_context = await reference_provider.get_references_for_claim(
            state, chunk, claim, claim_index
        )

        is_rag_mode = ref_context.retrieved_passages is not None

        result = await claim_verifier_agent.ainvoke(
            {
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "chunk": chunk.content,
                "claim": claim.claim,
                "evidence_context_explanation": format_evidence_explanation(
                    is_rag_mode
                ),
                "cited_references": ref_context.cited_references,
                "cited_references_paragraph": ref_context.cited_references_paragraph,
                "domain_context": format_domain_context(state.config.domain),
                "audience_context": format_audience_context(
                    state.config.target_audience
                ),
            }
        )

        if ref_context.retrieved_passages:
            result = result.model_copy(
                update={"retrieved_passages": ref_context.retrieved_passages}
            )

        substantiations.append(
            ClaimSubstantiationResultWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **result.model_dump(),
            )
        )

    return chunk.model_copy(update={"substantiations": substantiations})


@register_node(
    "Verify claims (citation-based)",
    "Verify the claims using citation-based references",
)
async def verify_claims(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    """Verify claims using citation-based references."""

    claim_verifier_agent = ClaimVerifierAgent(runtime.context)

    return await iterate_chunks(
        state,
        _verify_chunk_claims,
        "Verifying chunk claims",
        citation_provider=CitationBasedReferenceProvider(),
        claim_verifier_agent=claim_verifier_agent,
    )


@handle_chunk_errors("Claim verification")
async def _verify_chunk_claims(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    citation_provider: CitationBasedReferenceProvider,
    claim_verifier_agent: ClaimVerifierAgent,
) -> DocumentChunk:
    """Verify claims using citation-based references."""
    if chunk.citations is None:
        logger.debug(
            f"verify_claims: Chunk {chunk.chunk_index} has no citations detected, skipping verification"
        )
        return chunk

    return await _verify_chunk_claims_with_provider(
        state, chunk, citation_provider, claim_verifier_agent
    )


@register_node(
    "Verify claims (RAG)",
    "Verify the claims using RAG to retrieve relevant passages",
)
async def verify_claims_with_rag(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    """Verify claims using RAG to retrieve relevant passages."""

    rag_provider = RAGReferenceProvider(runtime.context.vector_store)
    claim_verifier_agent = ClaimVerifierAgent(runtime.context)

    return await iterate_chunks(
        state,
        _verify_chunk_claims_rag,
        "Verifying chunk claims with RAG",
        rag_provider=rag_provider,
        claim_verifier_agent=claim_verifier_agent,
    )


@handle_chunk_errors("Claim verification with RAG")
async def _verify_chunk_claims_rag(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    rag_provider: RAGReferenceProvider,
    claim_verifier_agent: ClaimVerifierAgent,
) -> DocumentChunk:
    """Verify claims using RAG-based references.

    RAG retrieves relevant passages directly based on claim text,
    without requiring citations to be detected first.
    """
    return await _verify_chunk_claims_with_provider(
        state, chunk, rag_provider, claim_verifier_agent
    )


def format_evidence_explanation(is_rag_mode: bool) -> str:
    evidence_explanation = (
        "### Evidence Retrieval Method: RAG (Retrieval-Augmented Generation)\n"
        "The supporting evidence below consists of **relevant passages retrieved via semantic search** from the supporting documents. "
        "These passages were selected based on their semantic similarity to the claim. "
        "Evaluate whether these retrieved passages provide sufficient support for the claim."
        if is_rag_mode
        else "### Evidence Retrieval Method: Citation-Based\n"
        "The supporting evidence below consists of **complete supporting documents** that are cited in the text. "
        "Review the full documents to determine if they support the claim."
    )

    return evidence_explanation
