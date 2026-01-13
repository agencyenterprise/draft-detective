import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.citation_detector import CitationResponseWithChunkIndex
from lib.agents.citation_detector_footnotes import CitationDetectorFootnotesAgent
from lib.agents.formatting_utils import format_bibliography_prompt_section
from lib.models.footnote_item import FootnoteItem
from lib.run_utils import run_tasks
from lib.workflows.chunk_iterator import get_target_chunks
from lib.workflows.citation_detection_footnotes.state import (
    CitationDetectionFootnotesState,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentChunk
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


def _format_footnotes_list(footnotes: List[FootnoteItem]) -> str:
    """Format footnotes as a numbered list."""
    if not footnotes:
        return "No footnotes available."

    lines = []
    for footnote in footnotes:
        # Format: [marker]. text
        lines.append(f"[{footnote.marker}]. {footnote.text}")

    return "\n".join(lines)


@register_node(
    "Detect citations (footnotes)",
    "Detect citations in the document using footnotes list",
)
async def detect_citations_footnotes(
    state: CitationDetectionFootnotesState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    citation_detector_agent = CitationDetectorFootnotesAgent(runtime.context)

    # Get target chunks based on config
    target_chunks = get_target_chunks(state)

    # Detect citations for each chunk
    tasks = [
        _detect_chunk_citations(state, chunk, citation_detector_agent)
        for chunk in target_chunks
    ]
    results = await run_tasks(tasks, desc="Detecting chunk citations (footnotes)")
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
    valid_citations = [
        citation for citation in detected_citations if citation is not None
    ]

    return {
        "citations": valid_citations,
        "errors": errors,
    }


async def _detect_chunk_citations(
    state: CitationDetectionFootnotesState,
    chunk: DocumentChunk,
    citation_detector_agent: CitationDetectorFootnotesAgent,
) -> CitationResponseWithChunkIndex:
    """Detect citations in a single chunk."""

    # Format footnotes as a list
    footnotes_list = _format_footnotes_list(state.footnotes)

    citations = await citation_detector_agent.ainvoke(
        {
            "footnotes_list": footnotes_list,
            "bibliography": format_bibliography_prompt_section(
                state.references, supporting_files=[]
            ),
            "chunk": chunk.content,
        }
    )
    return CitationResponseWithChunkIndex(
        chunk_index=chunk.chunk_index,
        **citations.model_dump(),
    )
