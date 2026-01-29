"""Graph definition for About This (Preface) validation workflow."""

from langgraph.graph import StateGraph

from lib.workflows.about_this.nodes.validate_preface import validate_preface
from lib.workflows.about_this.state import AboutThisState
from lib.workflows.context import ContextSchema


def build_about_this_graph() -> StateGraph:
    """Build the About This (Preface) validation workflow graph."""
    graph = StateGraph(AboutThisState, context_schema=ContextSchema)

    graph.add_node("validate_preface", validate_preface)
    graph.set_entry_point("validate_preface")
    graph.set_finish_point("validate_preface")

    return graph

