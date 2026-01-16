import logging

from langgraph.runtime import Runtime

from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.results_extraction.agents.results_extractor import (
    ResultsExtractorAgent,
)
from lib.workflows.results_extraction.state import ResultsExtractionState

logger = logging.getLogger(__name__)


@register_node(
    "Extract results",
    "Extract main results from the document and assess their reproducibility",
)
async def extract_results(
    state: ResultsExtractionState, runtime: Runtime[ContextSchema]
):
    file_artifacts_service = runtime.context.file_artifacts_service
    file_document = await file_artifacts_service.get_file_document(state.file_id)
    markdown = file_document.markdown

    logger.info("Extracting results from document")
    results_extractor_agent = ResultsExtractorAgent(runtime.context)
    response = await results_extractor_agent.ainvoke({"document": markdown})

    logger.info(f"Extracted {len(response.result_sections)} result sections")
    return {"results": response}
