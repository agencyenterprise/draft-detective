"""Chunked occurrence extraction for abbreviation scan v2.

prepare_chunks cuts the document into line ranges, distribute_chunks fans them
out with one Send each, and extract_chunk catalogues a single range. A failed
chunk costs only its own lines; the rest of the document is still catalogued.
"""

import logging
from typing import List

from langgraph.runtime import Runtime
from langgraph.types import Overwrite, Send

from lib.agents.abbreviation_chunk_extractor import (
    AbbreviationChunkExtractorAgent,
    PartialChunkExtractionError,
)
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    ChunkStatus,
)
from lib.workflows.abbreviation_scan_v2.layout import build_chunks
from lib.workflows.abbreviation_scan_v2.state import AbbreviationScanV2State
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.error_details import capture_error_details

logger = logging.getLogger(__name__)


@register_node("Prepare chunks")
async def prepare_chunks_node(
    state: AbbreviationScanV2State, runtime: Runtime[ContextSchema]
) -> dict:
    main_file = await runtime.context.file_artifacts_service.get_main_file()
    markdown = (main_file.markdown or "") if main_file else ""
    if not markdown.strip():
        logger.warning("[AbbreviationScanV2] Main file has no markdown content")
        return {"chunks": Overwrite([])}

    chunks = build_chunks(markdown, state.abbreviations_section_ranges)
    pending = sum(1 for c in chunks if c.status == ChunkStatus.PENDING)
    logger.info(
        f"[AbbreviationScanV2] Split document into {len(chunks)} chunks "
        f"({pending} to extract)"
    )
    return {"chunks": Overwrite(chunks)}


def distribute_chunks(state: AbbreviationScanV2State) -> List[Send] | str:
    """Fan out one extraction per pending chunk, or go straight to assembly."""
    pending = [c for c in state.chunks if c.status == ChunkStatus.PENDING]
    if not pending:
        return "assemble_catalogue"
    return [
        Send("extract_chunk", {"chunk": chunk.model_dump(mode="json")})
        for chunk in pending
    ]


@register_node("Extract abbreviations")
async def extract_chunk_node(state: dict, runtime: Runtime[ContextSchema]) -> dict:
    chunk = AbbreviationChunk.model_validate(state["chunk"])
    try:
        main_file = await runtime.context.file_artifacts_service.get_main_file()
        result, messages = await AbbreviationChunkExtractorAgent(runtime.context).ainvoke(
            {
                "markdown": main_file.markdown,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
        )
        update: dict = {
            "status": ChunkStatus.COMPLETED,
            "occurrences": result.occurrences,
            "messages": messages,
        }
    except PartialChunkExtractionError as e:
        # Keep what the model finished writing; the chunk stays flagged so the
        # gap shows up as a warning instead of silently missing occurrences.
        logger.warning(f"[AbbreviationScanV2] Chunk {chunk.chunk_index} truncated: {e}")
        update = {
            "status": ChunkStatus.PARTIAL,
            "occurrences": e.result.occurrences,
            "messages": e.messages,
            "error": str(e),
            "error_details": capture_error_details(e),
        }
    except Exception as e:
        logger.error(
            f"[AbbreviationScanV2] Chunk {chunk.chunk_index} failed: {e}", exc_info=True
        )
        update = {
            "status": ChunkStatus.ERROR,
            "error": str(e),
            "error_details": capture_error_details(e),
        }

    return {"chunks": [chunk.model_copy(update=update)]}
