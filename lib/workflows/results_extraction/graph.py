# lib/workflows/results_extraction/graph.py
from langgraph.graph import StateGraph
from lib.workflows.context import ContextSchema
from lib.workflows.results_extraction.nodes.extract_results import extract_results
from lib.workflows.results_extraction.state import ResultsExtractionState
import logging

logger = logging.getLogger(__name__)


def build_results_extraction_graph() -> StateGraph:
    graph = StateGraph(ResultsExtractionState, context_schema=ContextSchema)

    graph.add_node("extract_results", extract_results)
    graph.set_entry_point("extract_results")
    graph.set_finish_point("extract_results")

    return graph
