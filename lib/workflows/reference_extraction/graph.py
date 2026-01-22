"""Graph definition for reference extraction workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_extraction.nodes.detect_sections import (
    detect_sections_node,
)
from lib.workflows.reference_extraction.nodes.extract_text_references import (
    extract_text_references_node,
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

    1. detect_sections - Find reference/bibliography sections using lexical scan + density
    2. extract_text_references - Extract references with overlapping windows and deduplication

    Returns ExtractedReference list with unique IDs for each reference.
    """
    graph = StateGraph(ReferenceExtractionState, context_schema=ContextSchema)

    graph.add_node("detect_sections", detect_sections_node)
    graph.add_node("extract_text_references", extract_text_references_node)

    graph.set_entry_point("detect_sections")
    graph.add_edge("detect_sections", "extract_text_references")
    graph.set_finish_point("extract_text_references")

    return graph
