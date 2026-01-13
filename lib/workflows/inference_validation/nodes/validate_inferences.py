import logging

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.inference_validator import (
    InferenceValidationResponseWithClaimIndex,
    InferenceValidatorAgent,
)
from lib.agents.models import ClaimCategory
from lib.run_utils import run_tasks
from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.inference_validation.state import InferenceValidationState
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Validate inferences",
    "Validate the inferences for the claims",
)
async def validate_inferences(
    state: InferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Validate inferential claims using Toulmin model of argumentation."""

    inference_validator_agent = InferenceValidatorAgent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    target_chunks = await file_artifacts_service.get_chunks()
    document_summary = await file_artifacts_service.get_document_summary(state.file_id)

    # Process all chunks
    tasks = [
        _validate_chunk_inferences(
            state,
            chunk,
            target_chunks,
            document_summary,
            inference_validator_agent,
            file_artifacts_service,
        )
        for chunk in target_chunks
    ]

    results: tuple[
        list[list[InferenceValidationResponseWithClaimIndex] | None],
        list[Exception | None],
    ] = await run_tasks(tasks, desc="Validating inference claims")
    validation_results_raw, exceptions = results

    # Filter out None results
    validation_results: list[InferenceValidationResponseWithClaimIndex] = []
    for chunk_results in validation_results_raw:
        if chunk_results is not None:
            validation_results.extend(chunk_results)

    # Collect errors
    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            chunk_index = target_chunks[index].chunk_index
            errors.append(
                WorkflowError(
                    task_name="validate_inferences",
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )

    return {"inference_validations": validation_results, "errors": errors}


async def _validate_chunk_inferences(
    state: InferenceValidationState,
    chunk: AnalyzedChunk,
    chunks: list[AnalyzedChunk],
    document_summary: DocumentSummary,
    inference_validator_agent: InferenceValidatorAgent,
    file_artifacts_service: FileArtifactsServiceType,
) -> list[InferenceValidationResponseWithClaimIndex]:
    """Validate inferences for claims categorized as INTERPRETATION."""

    validation_results: list[InferenceValidationResponseWithClaimIndex] = []

    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping inference validation for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return validation_results

    # Skip if chunk has no categorization results
    if not chunk.claim_categories:
        logger.debug(
            "Skipping inference validation for chunk %s: no claim categories",
            chunk.chunk_index,
        )
        return validation_results

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
                    document_summary.summary if document_summary else ""
                ),
                "paragraph": file_artifacts_service.get_paragraph_text(
                    chunks, chunk.paragraph_index
                ),
                "chunk": chunk.content,
                "claim": claim.text,
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

    return validation_results
