import logging

from langgraph.runtime import Runtime

from lib.agents.claim_needs_substantiation_checker import (
    ClaimCommonKnowledgeResultWithClaimIndex,
    ClaimNeedsSubstantiationCheckerAgent,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
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


@requires_agent("needs_substantiation")
@handle_workflow_node_errors()
async def check_claim_needs_substantiation(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(
        f"check_claim_needs_substantiation ({state.config.session_id}): starting"
    )

    claim_needs_substantiation_checker_agent = ClaimNeedsSubstantiationCheckerAgent(
        runtime.context
    )

    results = await iterate_chunks(
        state,
        _check_chunk_claim_needs_substantiation,
        "Checking chunk claim needs substantiation",
        claim_needs_substantiation_checker_agent=claim_needs_substantiation_checker_agent,
    )
    logger.info(f"check_claim_needs_substantiation ({state.config.session_id}): done")
    return results


@handle_chunk_errors("Claim substantiation check")
async def _check_chunk_claim_needs_substantiation(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    claim_needs_substantiation_checker_agent: ClaimNeedsSubstantiationCheckerAgent,
) -> DocumentChunk:
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            f"check_claim_needs_substantiation: Chunk {chunk.chunk_index} has no claims to check"
        )
        return chunk

    claim_common_knowledge_results = []
    for claim_index, claim in enumerate(chunk.claims.claims):
        result = await claim_needs_substantiation_checker_agent.ainvoke(
            {
                "full_document": state.file.markdown,
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "chunk": chunk.content,
                "claim": claim.claim,
                "domain_context": format_domain_context(state.config.domain),
                "audience_context": format_audience_context(
                    state.config.target_audience
                ),
            }
        )

        claim_common_knowledge_results.append(
            ClaimCommonKnowledgeResultWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **result.model_dump(),
            )
        )

    return chunk.model_copy(
        update={"claim_common_knowledge_results": claim_common_knowledge_results}
    )
