from langgraph.graph import StateGraph

from lib.workflows.citation_detection.nodes.detect_citations import detect_citations
from lib.workflows.citation_detection.state import CitationDetectionState
from lib.workflows.context import ContextSchema


def build_citation_detection_graph() -> StateGraph:
    """
    Build a LangGraph workflow for citation detection.

    Args:
        config: Configuration for the citation detection workflow

    Returns:
        Configured StateGraph for citation detection workflow
    """

    graph = StateGraph(CitationDetectionState, context_schema=ContextSchema)

    # Add node
    graph.add_node("detect_citations", detect_citations)

    # Define flow
    graph.set_entry_point("detect_citations")
    graph.set_finish_point("detect_citations")

    return graph  # type: ignore[return-value]
