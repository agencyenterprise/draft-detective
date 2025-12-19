"""Graph definition for reference extraction workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_extraction.nodes.detect_sections import detect_sections
from lib.workflows.reference_extraction.nodes.extract_with_overlap import (
    extract_with_overlap,
)
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)


def build_reference_extraction_graph(
    config: ReferenceExtractionConfig = ReferenceExtractionConfig(),
) -> StateGraph:
    """
    Build reference extraction workflow graph.

    Two-phase extraction:
    1. Detect all reference sections (AI-based with regex fallback)
    2. Extract references using overlapping windows with incremental deduplication
    """
    graph = StateGraph(ReferenceExtractionState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("detect_sections", detect_sections)
    graph.add_node("extract_with_overlap", extract_with_overlap)

    # Define flow
    graph.set_entry_point("detect_sections")
    graph.add_edge("detect_sections", "extract_with_overlap")
    graph.set_finish_point("extract_with_overlap")

    return graph

