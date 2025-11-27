import logging

from langgraph.runtime import Runtime

from lib.agents.citation_detector import CitationDetectorAgent
from lib.agents.formatting_utils import format_bibliography_prompt_section
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.decorators import (
    handle_chunk_errors,
    handle_workflow_node_errors,
    requires_agent,
)

logger = logging.getLogger(__name__)


@requires_agent("citations")
@handle_workflow_node_errors()
async def detect_citations(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"detect_citations ({state.config.session_id}): starting")

    citation_detector_agent = CitationDetectorAgent(runtime.context)

    results = await iterate_chunks(
        state,
        _detect_chunk_citations,
        "Detecting chunk citations",
        citation_detector_agent=citation_detector_agent,
    )
    logger.info(f"detect_citations ({state.config.session_id}): done")
    return results


@handle_chunk_errors("Citation detection")
async def _detect_chunk_citations(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    citation_detector_agent: CitationDetectorAgent,
) -> DocumentChunk:
    citations = await citation_detector_agent.ainvoke(
        {
            "full_document": state.file.markdown,
            "bibliography": format_bibliography_prompt_section(state.references),
            "chunk": chunk.content,
            "feedback": "",
        }
    )
    return chunk.model_copy(update={"citations": citations})
