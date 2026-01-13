import logging

from langgraph.runtime import Runtime

from lib.agents.methodology_comparator import MethodologyComparisonAgent
from lib.agents.methodology_extractor import MethodologyExtractorAgent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.methodological_alignment.state import MethodologicalAlignmentState

logger = logging.getLogger(__name__)


@register_node(
    "Align methodology",
    "Compare the document's methodology to typical methods used in the broader field using web search",
)
async def align_methodology(
    state: MethodologicalAlignmentState, runtime: Runtime[ContextSchema]
):
    file_artifacts_service = runtime.context.file_artifacts_service
    file_document = await file_artifacts_service.get_file_document(state.file_id)
    markdown = file_document.markdown

    # Step 1: Extract methodology from document
    logger.info(f"align_methodology: Extracting methodology from document")
    methodology_extractor_agent = MethodologyExtractorAgent(runtime.context)
    extraction_response = await methodology_extractor_agent.ainvoke(
        {"document": markdown}
    )

    paper_methodology = extraction_response.methodology
    logger.info(
        f"align_methodology: Extracted methodology length: {len(paper_methodology)} characters"
    )

    # Step 2: Compare methodology to field standards using web search
    logger.info(f"align_methodology: Comparing methodology to field standards")
    methodology_comparison_agent = MethodologyComparisonAgent(runtime.context)
    comparison_response = await methodology_comparison_agent.ainvoke(
        {"extracted_methodology": extraction_response.methodology}
    )

    return {"methodology_comparison": comparison_response}
