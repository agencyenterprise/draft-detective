import logging

from langgraph.runtime import Runtime

from lib.agents.citation_detector import CitationDetectorAgent
from lib.agents.formatting_utils import format_bibliography_prompt_section
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    AnalyzedChunk,
    ClaimSubstantiatorState,
)
from lib.workflows.decorators import (
    handle_chunk_errors,
    register_node,
)

logger = logging.getLogger(__name__)


@register_node(
    "Detect citations",
    "Detect citations in the document",
)
async def detect_citations(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:

    citation_detector_agent = CitationDetectorAgent(runtime.context)

    return await iterate_chunks(
        state,
        _detect_chunk_citations,
        "Detecting chunk citations",
        citation_detector_agent=citation_detector_agent,
    )


@handle_chunk_errors("Citation detection")
async def _detect_chunk_citations(
    state: ClaimSubstantiatorState,
    chunk: AnalyzedChunk,
    citation_detector_agent: CitationDetectorAgent,
) -> AnalyzedChunk:
    citations = await citation_detector_agent.ainvoke(
        {
            "full_document": state.file.markdown,
            "bibliography": format_bibliography_prompt_section(state.references),
            "chunk": chunk.content,
            "feedback": "",
        }
    )
    return chunk.model_copy(update={"citations": citations})
