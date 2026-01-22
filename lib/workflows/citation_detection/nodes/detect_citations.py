import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.citation_detector import (
    CitationDetectorAgent,
    CitationResponseWithChunkIndex,
)
from lib.models.footnote_item import FootnoteItem
from lib.run_utils import run_tasks
from lib.workflows.citation_detection.state import CitationDetectionState
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError
from lib.workflows.reference_extraction.state import ExtractedReference

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


def _format_bibliography(references: List[ExtractedReference]) -> str:
    """Format extracted references as bibliography entries for the prompt."""
    if not references:
        return "No bibliography available."
    return "\n\n".join(
        f"### Bibliography entry #{i + 1}\n{ref.text}"
        for i, ref in enumerate(references)
    )


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

    # Format bibliography once for all chunks
    bibliography = _format_bibliography(references)

    # Detect citations for each chunk
    tasks = [
        _detect_chunk_citations(footnotes, bibliography, chunk, citation_detector_agent)
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
    footnotes: List[FootnoteItem],
    bibliography: str,
    chunk: AnalyzedChunk,
    citation_detector_agent: CitationDetectorAgent,
) -> CitationResponseWithChunkIndex:
    """Detect citations in a single chunk."""

    # Format footnotes as a list
    footnotes_list = _format_footnotes_list(footnotes)

    citations = await citation_detector_agent.ainvoke(
        {
            "footnotes_list": footnotes_list,
            "bibliography": bibliography,
            "chunk": chunk.content,
        }
    )
    return CitationResponseWithChunkIndex(
        chunk_index=chunk.chunk_index,
        **citations.model_dump(),
    )
