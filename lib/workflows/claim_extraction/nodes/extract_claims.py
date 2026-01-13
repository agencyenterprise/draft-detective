import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.claim_extractor import ClaimExtractorAgent, ClaimResponseWithChunkIndex
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.run_utils import run_tasks
from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.claim_extraction.state import ClaimExtractionState
from lib.workflows.claim_substantiation.state import AnalyzedChunk
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
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    target_chunks = await file_artifacts_service.get_chunks()
    document_summary = await file_artifacts_service.get_document_summary(state.file_id)

    # Extract claims for each chunk
    tasks = [
        _extract_chunk_claims(
            state,
            chunk,
            target_chunks,
            document_summary,
            claim_extractor_agent=claim_extractor_agent,
            file_artifacts_service=file_artifacts_service,
        )
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
    chunk: AnalyzedChunk,
    chunks: List[AnalyzedChunk],
    document_summary: DocumentSummary,
    claim_extractor_agent: ClaimExtractorAgent,
    file_artifacts_service: FileArtifactsServiceType,
) -> ClaimResponseWithChunkIndex:
    """Extract claims from a single chunk."""

    claims = await claim_extractor_agent.ainvoke(
        {
            "chunk": chunk.content,
            "paragraph": file_artifacts_service.get_paragraph_text(
                chunks, chunk.paragraph_index
            ),
            "summarized_argument": (
                document_summary.summary if document_summary else ""
            ),
            "domain_context": format_domain_context(state.config.domain),
            "audience_context": format_audience_context(state.config.target_audience),
        }
    )

    return ClaimResponseWithChunkIndex(
        chunk_index=chunk.chunk_index,
        **claims.model_dump(),
    )
