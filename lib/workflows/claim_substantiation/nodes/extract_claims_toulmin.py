import logging

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.agents.toulmin_claim_extractor import ToulminClaimExtractorAgent
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
    "Extract claims (Toulmin)",
    "Extract claims using the Toulmin model",
)
async def extract_claims_toulmin(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    toulmin_claim_extractor_agent = ToulminClaimExtractorAgent(runtime.context)

    return await iterate_chunks(
        state,
        _extract_chunk_claims_toulmin,
        "Extracting chunk claims (Toulmin)",
        toulmin_claim_extractor_agent=toulmin_claim_extractor_agent,
    )


@handle_chunk_errors("Toulmin claim extraction")
async def _extract_chunk_claims_toulmin(
    state: ClaimSubstantiatorState,
    chunk: AnalyzedChunk,
    toulmin_claim_extractor_agent: ToulminClaimExtractorAgent,
) -> AnalyzedChunk:
    claims = await toulmin_claim_extractor_agent.ainvoke(
        {
            "chunk": chunk.content,
            "full_document": state.file.markdown,
            "domain_context": format_domain_context(state.config.domain),
            "audience_context": format_audience_context(state.config.target_audience),
            "paragraph": state.get_paragraph(chunk.paragraph_index),
        }
    )
    return chunk.model_copy(update={"claims": claims})
