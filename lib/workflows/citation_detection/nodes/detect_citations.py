import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.citation_detector import (
    BatchedCitationResult,
    CitationDetectorAgent,
    CitationDetectorPromptKwargs,
    CitationResponse,
)
from lib.models.footnote_item import FootnoteItem
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.citation_detection.state import CitationDetectionState
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import ExtractedReference

logger = logging.getLogger(__name__)

# Number of chunks to process per LLM call
CHUNKS_PER_BATCH = 20


def _format_footnotes_list(footnotes: List[FootnoteItem]) -> str:
    """Format footnotes as a numbered list."""
    if not footnotes:
        return "No footnotes available."

    lines = []
    for footnote in footnotes:
        # Format: [marker]. text
        lines.append(f"[{footnote.marker}]. {footnote.text}")

    return "\n".join(lines)


def _format_bibliography(references: List[ExtractedReference]) -> str:
    """Format extracted references as bibliography entries for the prompt."""
    if not references:
        return "No bibliography available."
    return "\n\n".join(
        f"### Bibliography entry #{i + 1} (id `{ref.id}`)\n\n{ref.text}"
        for i, ref in enumerate(references)
    )


def _batch_chunks(
    chunks: List[AnalyzedChunk], batch_size: int
) -> List[List[AnalyzedChunk]]:
    """Split chunks into batches of specified size."""
    return [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]


@register_node(
    "Detect citations",
    "Detect citations in the document",
)
async def detect_citations(
    state: CitationDetectionState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    citation_detector_agent = CitationDetectorAgent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    # Use extracted references (no file matching needed for citation detection)
    references = await file_artifacts_service.get_extracted_references()
    target_chunks = await file_artifacts_service.get_chunks()
    footnotes = await file_artifacts_service.get_footnotes()

    # Format shared context once for all chunks
    bibliography = _format_bibliography(references)
    footnotes_list = _format_footnotes_list(footnotes)

    # Batch chunks for efficient LLM processing
    batches = _batch_chunks(target_chunks, CHUNKS_PER_BATCH)
    logger.info(
        f"Processing {len(target_chunks)} chunks in {len(batches)} batches "
        f"(batch size: {CHUNKS_PER_BATCH})"
    )

    # Create tasks for each batch
    tasks = [
        _detect_batch_citations(
            footnotes_list, bibliography, batch, citation_detector_agent
        )
        for batch in batches
    ]
    results = await run_tasks(tasks, desc="Detecting chunk citations")
    batch_results, exceptions = results

    # Collect errors - use first chunk index of each batch for error reporting
    batch_first_indices = [batch[0].chunk_index for batch in batches]
    errors = convert_exceptions_to_workflow_errors(
        "_detect_chunk_citations",
        exceptions,
        batch_first_indices,
        workflow_run_id=runtime.context.workflow_run_id,
    )

    # Flatten batch results into individual chunk citations
    valid_citations: List[CitationResponse] = []
    for batch_result in batch_results:
        if batch_result is not None:
            valid_citations.extend(batch_result.results)

    return {
        "citations": valid_citations,
        "errors": errors,
    }


async def _detect_batch_citations(
    footnotes_list: str,
    bibliography: str,
    chunks: List[AnalyzedChunk],
    citation_detector_agent: CitationDetectorAgent,
) -> BatchedCitationResult:
    """Detect citations in a batch of chunks."""

    # Convert chunks to (index, content) tuples for the agent
    chunk_tuples = [(chunk.chunk_index, chunk.content) for chunk in chunks]

    prompt_kwargs: CitationDetectorPromptKwargs = {
        "footnotes_list": footnotes_list,
        "bibliography": bibliography,
        "chunks": chunk_tuples,
    }
    return await citation_detector_agent.ainvoke(prompt_kwargs)
