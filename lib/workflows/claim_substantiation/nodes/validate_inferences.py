import logging

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.agents.inference_validator import (
    InferenceValidationResponseWithClaimIndex,
    InferenceValidatorAgent,
)
from lib.agents.models import ClaimCategory
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.decorators import handle_chunk_errors, register_node

logger = logging.getLogger(__name__)


@register_node(
    "Validate inferences",
    "Validate the inferences for the claims",
)
async def validate_inferences(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    """Validate inferential claims using Toulmin model of argumentation."""

    inference_validator_agent = InferenceValidatorAgent(runtime.context)

    return await iterate_chunks(
        state,
        _validate_chunk_inferences,
        "Validating inference claims",
        inference_validator_agent=inference_validator_agent,
    )


@handle_chunk_errors("Inference validation")
async def _validate_chunk_inferences(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    inference_validator_agent: InferenceValidatorAgent,
) -> DocumentChunk:
    """Validate inferences for claims categorized as INTERPRETATION."""
    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping inference validation for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return chunk

    # Skip if chunk has no categorization results
    if not chunk.claim_categories:
        logger.debug(
            "Skipping inference validation for chunk %s: no claim categories",
            chunk.chunk_index,
        )
        return chunk

    validation_results = []
    for claim_index, claim in enumerate(chunk.claims.claims):
        # Find the categorization result for this claim
        categorization = next(
            (cat for cat in chunk.claim_categories if cat.claim_index == claim_index),
            None,
        )

        # Only validate claims categorized as INTERPRETATION
        if (
            categorization is None
            or categorization.claim_category != ClaimCategory.INTERPRETATION
        ):
            logger.debug(
                "Skipping claim %s in chunk %s: not an inferential claim (category: %s)",
                claim_index,
                chunk.chunk_index,
                categorization.claim_category if categorization else "None",
            )
            continue

        logger.debug(
            "Validating inference for claim %s in chunk %s",
            claim_index,
            chunk.chunk_index,
        )

        result = await inference_validator_agent.ainvoke(
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
                "audience_context": format_audience_context(
                    state.config.target_audience
                ),
            }
        )
        validation_results.append(
            InferenceValidationResponseWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **result.model_dump(),
            )
        )

    logger.debug(
        "Validated %s inference claims for chunk %s",
        len(validation_results),
        chunk.chunk_index,
    )

    return chunk.model_copy(update={"inference_validations": validation_results})
