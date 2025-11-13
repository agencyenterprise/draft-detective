import logging
from lib.agents.citation_suggester import (
    CitationSuggestionResponse,
    CitationSuggestionResultWithClaimIndex,
    citation_suggester_agent,
)
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.agents.formatting_utils import (
    format_cited_references,
    format_bibliography_prompt_section,
)
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


@handle_workflow_node_errors()
async def suggest_citations(
    state: ClaimSubstantiatorState,
) -> ClaimSubstantiatorState:
    logger.info(f"suggest_citations ({state.config.session_id}): starting")

    if not state.config.run_suggest_citations:
        logger.info(
            f"suggest_citations ({state.config.session_id}): skipping citations suggestion (run_suggest_citations is False)"
        )
        return {}

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "suggest_citations" not in agents_to_run:
        logger.info(
            f"suggest_citations ({state.config.session_id}): Skipping citations suggestion (not in agents_to_run)"
        )
        return {}

    logger.info(f"suggest_citations ({state.config.session_id}): done")

    return await iterate_chunks(
        state, _suggest_chunk_citations, "Suggesting chunk citations"
    )


async def _suggest_chunk_citations(
    state: ClaimSubstantiatorState, chunk: DocumentChunk
) -> DocumentChunk:
    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping citation suggestions for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return chunk

    citation_suggestions = []
    for claim_index, claim in enumerate(chunk.claims.claims):
        category = next(
            (
                result
                for result in chunk.claim_categories
                if result.claim_index == claim_index
            ),
            None,
        )
        if category and not category.needs_external_verification:
            continue

        cited_references = format_cited_references(
            state.references,
            state.supporting_files,
            chunk.citations,
            truncate_at_character_count=1000,  # Include only a little bit of the text of the references
        )

        result = await citation_suggester_agent.ainvoke(
            {
                "full_document": state.file.markdown,
                "bibliography": format_bibliography_prompt_section(
                    state.references, state.supporting_documents_summaries
                ),
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "chunk": chunk.content,
                "claim": claim.claim,
                "cited_references": cited_references,
                "literature_review_report": state.literature_review,
            }
        )
        citation_suggestions.append(
            CitationSuggestionResultWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **result.model_dump(),
            )
        )

    return chunk.model_copy(update={"citation_suggestions": citation_suggestions})
