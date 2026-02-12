import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.claim_verifier import (
    ClaimSubstantiationResultWithClaimIndex,
    ClaimVerifierAgent,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.models.bibliography_item import BibliographyItem
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.claim_reference_validation.reference_providers import (
    RAGReferenceProvider,
    get_all_paragraph_citations,
)
from lib.workflows.claim_reference_validation.state import ClaimReferenceValidationState
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import ClaimExtractionVersion

logger = logging.getLogger(__name__)


def _needs_substantiation(
    chunks: List[AnalyzedChunk],
    chunk: AnalyzedChunk,
    claim_index: int,
    claim_extraction_version: ClaimExtractionVersion = ClaimExtractionVersion.V1,
) -> bool:
    """
    Check if a claim needs substantiation.

    For v1:
        A claim needs substantiation if:
        1. It has citations in the paragraph that includes the chunk; AND
        2. It needs external verification (from categorizer, or all claims if no categorization)

    For v2:
        A claim needs substantiation if:
        1. It has citations in the paragraph that includes the chunk; AND
        2. The claim-level needs_external_verification flag is set (or True if flag is missing)
    """

    paragraph_citations = get_all_paragraph_citations(chunks, chunk)
    if len(paragraph_citations) == 0:
        # If there's no citations in the paragraph, skip verification since there's no document to verify against
        return False

    if claim_extraction_version == ClaimExtractionVersion.V2:
        # V2: use claim-level verification signal
        if chunk.claims is None or claim_index >= len(chunk.claims.claims):
            return True
        claim = chunk.claims.claims[claim_index]
        if claim.needs_external_verification is None:
            # Safety fallback: if flag not set, verify
            return True
        return claim.needs_external_verification

    # V1: use category-driven logic
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
    chunks: List[AnalyzedChunk],
    chunk: AnalyzedChunk,
    rag_provider: RAGReferenceProvider,
    claim_verifier_agent: ClaimVerifierAgent,
    file_artifacts_service: FileArtifactsServiceType,
    supporting_files: List[FileDocument],
    references: List[BibliographyItem],
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

    claim_extraction_version = state.config.claim_extraction_version
    substantiations = []

    for claim_index, claim in enumerate(chunk.claims.claims):

        if not _needs_substantiation(
            chunks, chunk, claim_index, claim_extraction_version
        ):
            logger.debug(
                f"Chunk {chunk.chunk_index} claim {claim_index} does not need external verification, skipping verification"
            )
            continue

        ref_context = await rag_provider.get_references_for_claim(
            chunks, supporting_files, references, chunk, claim, claim_index
        )

        result = await claim_verifier_agent.ainvoke(
            {
                "paragraph": file_artifacts_service.get_paragraph_text(
                    chunks, chunk.paragraph_index
                ),
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
):
    """Verify chunk claims using RAG reference provider.

    Returns a list of substantiation results instead of updating the chunk.
    Skips chunks with no claims.
    """

    file_artifacts_service = runtime.context.file_artifacts_service
    rag_provider = RAGReferenceProvider(runtime.context.vector_store)
    claim_verifier_agent = ClaimVerifierAgent(runtime.context)

    # Fetch artifacts from file artifacts service
    target_chunks = await file_artifacts_service.get_chunks()
    supporting_files = await file_artifacts_service.get_supporting_files()
    references = await file_artifacts_service.get_references()

    tasks = [
        _verify_chunk_claims_with_provider(
            state,
            target_chunks,
            chunk,
            rag_provider,
            claim_verifier_agent,
            file_artifacts_service,
            supporting_files,
            references,
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

    chunk_indices = [c.chunk_index for c in target_chunks]
    errors = convert_exceptions_to_workflow_errors(
        "verify_claims",
        exceptions,
        chunk_indices,
        workflow_run_id=runtime.context.workflow_run_id,
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
