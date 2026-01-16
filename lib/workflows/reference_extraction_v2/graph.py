"""Graph definition for reference extraction v2 workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_extraction_v2.nodes.extract_references import (
    extract_references_node,
)
from lib.workflows.reference_extraction_v2.state import ReferenceExtractionV2State


def build_reference_extraction_v2_graph() -> StateGraph:
    """
    Build reference extraction v2 workflow graph.

    Single-node workflow that uses an AI agent with document search
    to extract bibliographic references.
    """
    graph = StateGraph(ReferenceExtractionV2State, context_schema=ContextSchema)

    graph.add_node("extract_references", extract_references_node)

    graph.set_entry_point("extract_references")
    graph.set_finish_point("extract_references")

    return graph
