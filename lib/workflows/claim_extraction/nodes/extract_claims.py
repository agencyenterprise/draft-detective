import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.claim_extractor import ClaimExtractorAgent, ClaimResponseWithChunkIndex
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.run_utils import run_tasks
from lib.workflows.chunk_iterator import get_target_chunks
from lib.workflows.claim_extraction.state import ClaimExtractionState
from lib.workflows.document_processing.state import DocumentChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Extract claims",
    "Extract claims from the document",
)
async def extract_claims(
    state: ClaimExtractionState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    claim_extractor_agent = ClaimExtractorAgent(runtime.context)

    # Get target chunks based on config
    target_chunks = get_target_chunks(state)

    # Extract claims for each chunk
    tasks = [
        _extract_chunk_claims(state, chunk, claim_extractor_agent)
        for chunk in target_chunks
    ]
    results = await run_tasks(tasks, desc="Extracting chunk claims")
    extracted_claims, exceptions = results

    # Collect errors
    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            chunk_index = target_chunks[index].chunk_index
            errors.append(
                WorkflowError(
                    task_name="_extract_chunk_claims",
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )

    # Filter out None results (from errors)
    valid_claims: List[ClaimResponseWithChunkIndex] = [
        claim for claim in extracted_claims if claim is not None
    ]

    return {
        "claims": valid_claims,
        "errors": errors,
    }


async def _extract_chunk_claims(
    state: ClaimExtractionState,
    chunk: DocumentChunk,
    claim_extractor_agent: ClaimExtractorAgent,
) -> ClaimResponseWithChunkIndex:
    """Extract claims from a single chunk."""

    claims = await claim_extractor_agent.ainvoke(
        {
            "chunk": chunk.content,
            "paragraph": state.get_paragraph(chunk.paragraph_index),
            "summarized_argument": (
                state.main_document_summary.summary
                if state.main_document_summary
                else ""
            ),
            "domain_context": format_domain_context(state.config.domain),
            "audience_context": format_audience_context(state.config.target_audience),
        }
    )

    return ClaimResponseWithChunkIndex(
        chunk_index=chunk.chunk_index,
        **claims.model_dump(),
    )
