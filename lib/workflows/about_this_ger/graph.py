"""Graph definition for About This (GER) workflow.

Two deep-agent nodes run in parallel: one validates the preface section,
the other validates author biographies.
"""

from langgraph.graph import START, StateGraph
from langgraph.graph.state import END

from lib.workflows.about_this_ger.nodes.validate_authors_deep import (
    validate_authors_deep,
)
from lib.workflows.about_this_ger.nodes.validate_preface_deep import (
    validate_preface_deep,
)
from lib.workflows.about_this_ger.state import AboutThisGerState
from lib.workflows.context import ContextSchema


def build_about_this_ger_graph():
    """Build the About This (GER) workflow graph with parallel nodes."""

    graph = StateGraph(AboutThisGerState, context_schema=ContextSchema)

    graph.add_node("validate_preface_deep", validate_preface_deep)
    graph.add_node("validate_authors_deep", validate_authors_deep)

    graph.add_edge(START, "validate_preface_deep")
    graph.add_edge(START, "validate_authors_deep")
    graph.add_edge(["validate_preface_deep", "validate_authors_deep"], END)

    return graph
