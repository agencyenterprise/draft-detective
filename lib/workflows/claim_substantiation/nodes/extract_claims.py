import logging

from langgraph.runtime import Runtime

from lib.agents.claim_extractor import ClaimExtractorAgent
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.decorators import (
    handle_chunk_errors,
    register_node,
)

logger = logging.getLogger(__name__)


@register_node(
    "Extract claims",
    "Extract claims from the document",
)
async def extract_claims(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    claim_extractor_agent = ClaimExtractorAgent(runtime.context)

    return await iterate_chunks(
        state,
        _extract_chunk_claims,
        "Extracting chunk claims",
        claim_extractor_agent=claim_extractor_agent,
    )


@handle_chunk_errors("Claim extraction")
async def _extract_chunk_claims(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    claim_extractor_agent: ClaimExtractorAgent,
) -> DocumentChunk:
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
    return chunk.model_copy(update={"claims": claims})
