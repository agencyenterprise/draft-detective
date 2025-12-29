import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.claim_verifier import (
    ClaimSubstantiationResultWithClaimIndex,
    ClaimVerifierAgent,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.run_utils import run_tasks
from lib.workflows.chunk_iterator import get_target_chunks
from lib.workflows.claim_reference_validation.state import ClaimReferenceValidationState
from lib.workflows.claim_substantiation.reference_providers import (
    RAGReferenceProvider,
    get_all_paragraph_citations,
)
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.base import WorkflowError

logger = logging.getLogger(__name__)


def _needs_substantiation(
    state: ClaimReferenceValidationState, chunk: AnalyzedChunk, claim_index: int
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
    state: ClaimReferenceValidationState,
    chunk: AnalyzedChunk,
    rag_provider: RAGReferenceProvider,
    claim_verifier_agent: ClaimVerifierAgent,
) -> List[ClaimSubstantiationResultWithClaimIndex]:
    """Verify chunk claims using RAG reference provider.

    Returns a list of substantiation results instead of updating the chunk.
    Skips chunks with no claims. For each claim:
    - ALWAYS verifies if the chunk has citations (even if common knowledge)
    - Verifies if the claim needs substantiation (not common knowledge)

    This ensures all citations are validated regardless of common knowledge status.
    """
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(f"Chunk {chunk.chunk_index} has no claims")
        return []

    substantiations = []

    for claim_index, claim in enumerate(chunk.claims.claims):
        if not _needs_substantiation(state, chunk, claim_index):
            logger.debug(
                f"Chunk {chunk.chunk_index} claim {claim_index} does not need external verification, skipping verification"
            )
            continue

        ref_context = await rag_provider.get_references_for_claim(
            state, chunk, claim, claim_index
        )

        result = await claim_verifier_agent.ainvoke(
            {
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "chunk": chunk.content,
                "claim": claim.claim,
                "evidence_context_explanation": format_evidence_explanation(),
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

    return substantiations


@register_node(
    "Verify claims (RAG)",
    "Verify the claims using RAG to retrieve relevant passages",
)
async def verify_claims(
    state: ClaimReferenceValidationState, runtime: Runtime[ContextSchema]
) -> ClaimReferenceValidationState:
    """Verify claims using RAG to retrieve relevant passages."""

    rag_provider = RAGReferenceProvider(runtime.context.vector_store)
    claim_verifier_agent = ClaimVerifierAgent(runtime.context)

    target_chunks = get_target_chunks(state)

    tasks = [
        _verify_chunk_claims_with_provider(
            state, chunk, rag_provider, claim_verifier_agent
        )
        for chunk in target_chunks
    ]
    results: tuple[
        list[List[ClaimSubstantiationResultWithClaimIndex]], list[Exception]
    ] = await run_tasks(tasks, desc="Verifying chunk claims with RAG")
    substantiations_lists, exceptions = results

    all_substantiations: List[ClaimSubstantiationResultWithClaimIndex] = []
    for substantiations_list in substantiations_lists:
        if substantiations_list is not None:
            all_substantiations.extend(substantiations_list)

    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            chunk_index = target_chunks[index].chunk_index
            errors.append(
                WorkflowError(
                    task_name="verify_claims",
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )

    return {"substantiations": all_substantiations, "errors": errors}


def format_evidence_explanation() -> str:
    """Format evidence explanation for RAG mode."""
    return (
        "### Evidence Retrieval Method: RAG (Retrieval-Augmented Generation)\n"
        "The supporting evidence below consists of **relevant passages retrieved via semantic search** from the supporting documents. "
        "These passages were selected based on their semantic similarity to the claim. "
        "Evaluate whether these retrieved passages provide sufficient support for the claim."
    )
