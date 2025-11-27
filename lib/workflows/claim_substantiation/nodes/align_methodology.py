import logging

from langgraph.runtime import Runtime

from lib.agents.methodology_comparator import MethodologyComparisonAgent
from lib.agents.methodology_extractor import MethodologyExtractorAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Align methodology",
    "Compare the document's methodology to typical methods used in the broader field using web search",
)
async def align_methodology(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    if not state.config.run_align_methods:
        logger.info(
            f"align_methodology ({state.config.session_id}): skipping methodology alignment (run_align_methods is False)"
        )
        return {}

    markdown = state.file.markdown

    # Step 1: Extract methodology from document
    logger.info(
        f"align_methodology ({state.config.session_id}): Extracting methodology from document"
    )
    methodology_extractor_agent = MethodologyExtractorAgent(runtime.context)
    extraction_response = await methodology_extractor_agent.ainvoke(
        {"document": markdown}
    )

    paper_methodology = extraction_response.methodology
    logger.info(
        f"align_methodology ({state.config.session_id}): Extracted methodology length: {len(paper_methodology)} characters"
    )

    # Step 2: Compare methodology to field standards using web search
    logger.info(
        f"align_methodology ({state.config.session_id}): Comparing methodology to field standards"
    )
    methodology_comparison_agent = MethodologyComparisonAgent(runtime.context)
    comparison_response = await methodology_comparison_agent.ainvoke(
        {"paper_methodology": paper_methodology}
    )

    return {"methodology_comparison": comparison_response}
