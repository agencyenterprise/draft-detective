# lib/workflows/results_extraction/nodes/extract_results.py
import logging
from langgraph.runtime import Runtime
from lib.workflows.results_extraction.agents.results_extractor import (
    ResultsExtractorAgent,
    ResultsListResponse,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.results_extraction.state import ResultsExtractionState

logger = logging.getLogger(__name__)


@register_node(
    "Extract results",
    "Extract main results from the document and assess their reproducibility",
)
async def extract_results(
    state: ResultsExtractionState, runtime: Runtime[ContextSchema]
) -> ResultsExtractionState:
    markdown = state.file.markdown

    logger.info("Extracting results from document")
    results_extractor_agent = ResultsExtractorAgent(runtime.context)
    response = await results_extractor_agent.ainvoke({"document": markdown})

    logger.info(f"Extracted {len(response.result_sections)} result sections")
    return {"results": ResultsListResponse(**response.model_dump())}
