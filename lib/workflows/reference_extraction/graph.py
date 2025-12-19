"""Graph definition for reference extraction workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_extraction.nodes.extract_references import (
    extract_references,
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

    Extracts references from the document and matches them with supporting documents.
    """
    graph = StateGraph(ReferenceExtractionState, context_schema=ContextSchema)

    # Add node
    graph.add_node("extract_references", extract_references)

    # Define flow
    graph.set_entry_point("extract_references")
    graph.set_finish_point("extract_references")

    return graph
