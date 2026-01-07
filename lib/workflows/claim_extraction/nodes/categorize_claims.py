import logging
from typing import Any, Dict, List, Optional

from langgraph.runtime import Runtime

from lib.agents.claim_categorizer import (
    ClaimCategorizationResponseWithClaimIndex,
    ClaimCategorizerAgent,
)
from lib.agents.claim_extractor import Claim, ClaimResponseWithChunkIndex
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.run_utils import run_tasks
from lib.workflows.claim_extraction.state import ClaimExtractionState
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Categorize claims",
    "Categorize claims into categories",
)
async def categorize_claims(
    state: ClaimExtractionState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    claim_categorizer_agent = ClaimCategorizerAgent(runtime.context)

    # Build list of (claim_response, claim_index) tuples for all claims
    claim_tasks = []
    for claim_response in state.claims:
        if not claim_response.claims:
            continue
        for claim_index, claim in enumerate(claim_response.claims):
            claim_tasks.append((claim_response, claim_index, claim))

    # Categorize all claims
    tasks = [
        _categorize_single_claim(
            state, claim_response, claim_index, claim, claim_categorizer_agent
        )
        for claim_response, claim_index, claim in claim_tasks
    ]
    results = await run_tasks(tasks, desc="Categorizing claims")
    categorizations, exceptions = results

    # Collect errors
    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            claim_response, claim_index, _ = claim_tasks[index]
            errors.append(
                WorkflowError(
                    task_name="_categorize_single_claim",
                    error=str(exception),
                    chunk_index=claim_response.chunk_index,
                )
            )

    # Filter out None results (from errors)
    valid_categorizations: List[ClaimCategorizationResponseWithClaimIndex] = [
        cat for cat in categorizations if cat is not None
    ]

    return {
        "claim_categories": valid_categorizations,
        "errors": errors,
    }


async def _categorize_single_claim(
    state: ClaimExtractionState,
    claim_response: ClaimResponseWithChunkIndex,
    claim_index: int,
    claim: Claim,
    claim_categorizer_agent: ClaimCategorizerAgent,
) -> Optional[ClaimCategorizationResponseWithClaimIndex]:
    """Categorize a single claim."""

    # Find the chunk for this claim
    chunk = next(
        (c for c in state.chunks if c.chunk_index == claim_response.chunk_index),
        None,
    )
    if chunk is None:
        logger.warning(
            f"Chunk {claim_response.chunk_index} not found for claim {claim_index}"
        )
        return None

    result = await claim_categorizer_agent.ainvoke(
        {
            "document_summary": (
                state.main_document_summary.summary
                if state.main_document_summary
                else ""
            ),
            "paragraph": state.get_paragraph(chunk.paragraph_index),
            "chunk": chunk.content,
            "claim": claim.claim,
            "domain_context": format_domain_context(state.config.domain),
            "audience_context": format_audience_context(state.config.target_audience),
        }
    )
    return ClaimCategorizationResponseWithClaimIndex(
        chunk_index=claim_response.chunk_index,
        claim_index=claim_index,
        **result.model_dump(),
    )
