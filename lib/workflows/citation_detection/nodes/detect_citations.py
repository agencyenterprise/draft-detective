import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.citation_detector import (
    CitationDetectorAgent,
    CitationResponseWithChunkIndex,
)
from lib.agents.formatting_utils import format_bibliography_prompt_section
from lib.run_utils import run_tasks
from lib.workflows.chunk_iterator import get_target_chunks
from lib.workflows.citation_detection.state import CitationDetectionState
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentChunk
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Detect citations",
    "Detect citations in the document",
)
async def detect_citations(
    state: CitationDetectionState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    citation_detector_agent = CitationDetectorAgent(runtime.context)

    # Get target chunks based on config
    target_chunks = get_target_chunks(state)

    # Detect citations for each chunk
    tasks = [
        _detect_chunk_citations(state, chunk, citation_detector_agent)
        for chunk in target_chunks
    ]
    results = await run_tasks(tasks, desc="Detecting chunk citations")
    detected_citations, exceptions = results

    # Collect errors
    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            chunk_index = target_chunks[index].chunk_index
            errors.append(
                WorkflowError(
                    task_name="_detect_chunk_citations",
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )

    # Filter out None results (from errors)
    valid_citations: List[CitationResponseWithChunkIndex] = [
        citation for citation in detected_citations if citation is not None
    ]

    return {
        "citations": valid_citations,
        "errors": errors,
    }


async def _detect_chunk_citations(
    state: CitationDetectionState,
    chunk: DocumentChunk,
    citation_detector_agent: CitationDetectorAgent,
) -> CitationResponseWithChunkIndex:
    """Detect citations in a single chunk."""
    citations = await citation_detector_agent.ainvoke(
        {
            "full_document": state.file.markdown,
            "bibliography": format_bibliography_prompt_section(state.references),
            "chunk": chunk.content,
            "feedback": "",
        }
    )
    return CitationResponseWithChunkIndex(
        chunk_index=chunk.chunk_index,
        **citations.model_dump(),
    )
