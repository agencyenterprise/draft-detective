from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reviewer_2.nodes.generate_review import generate_review
from lib.workflows.reviewer_2.state import Reviewer2State


def build_reviewer_2_graph():
    """Build the Reviewer 2 workflow graph."""
    graph = StateGraph(Reviewer2State, context_schema=ContextSchema)

    graph.add_node("generate_review", generate_review)
    graph.set_entry_point("generate_review")
    graph.set_finish_point("generate_review")

    return graph  # type: ignore[return-value]
