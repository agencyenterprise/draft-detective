"""Graph definition for About Authors validation workflow."""

from langgraph.graph import StateGraph

from lib.workflows.about_authors.nodes.validate_authors import validate_authors
from lib.workflows.about_authors.state import AboutAuthorsState
from lib.workflows.context import ContextSchema


def build_about_authors_graph() -> StateGraph:
    """Build the About Authors validation workflow graph."""
    graph = StateGraph(AboutAuthorsState, context_schema=ContextSchema)

    graph.add_node("validate_authors", validate_authors)
    graph.set_entry_point("validate_authors")
    graph.set_finish_point("validate_authors")

    return graph

