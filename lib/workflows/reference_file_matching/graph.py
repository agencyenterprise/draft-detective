"""Graph definition for reference file matching workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_file_matching.nodes.match_supporting_docs import (
    match_supporting_docs_node,
)
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)


def build_reference_file_matching_graph(
    config: ReferenceFileMatchingConfig = ReferenceFileMatchingConfig(),
) -> StateGraph:
    """
    Build reference file matching workflow graph.

    1. match_supporting_docs - Match extracted references to supporting documents

    Returns ReferenceFileMatch list linking reference IDs to file IDs.
    """
    graph = StateGraph(ReferenceFileMatchingState, context_schema=ContextSchema)

    graph.add_node("match_supporting_docs", match_supporting_docs_node)

    graph.set_entry_point("match_supporting_docs")
    graph.set_finish_point("match_supporting_docs")

    return graph
