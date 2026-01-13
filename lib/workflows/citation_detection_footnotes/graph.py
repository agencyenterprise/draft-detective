from langgraph.graph import StateGraph

from lib.workflows.citation_detection_footnotes.nodes.detect_citations_footnotes import (
    detect_citations_footnotes,
)
from lib.workflows.citation_detection_footnotes.state import (
    CitationDetectionFootnotesState,
)
from lib.workflows.context import ContextSchema


def build_citation_detection_footnotes_graph() -> StateGraph:
    """Build a LangGraph workflow for citation detection with footnotes."""

    graph = StateGraph(CitationDetectionFootnotesState, context_schema=ContextSchema)

    # Add node
    graph.add_node("detect_citations_footnotes", detect_citations_footnotes)

    # Define flow
    graph.set_entry_point("detect_citations_footnotes")
    graph.set_finish_point("detect_citations_footnotes")

    return graph
