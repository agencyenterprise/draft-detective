"""Graph definition for abbreviation scan v2 workflow."""

from langgraph.graph import StateGraph

from lib.workflows.abbreviation_scan_v2.nodes.apply_ignored_list import (
    apply_ignored_list_node,
)
from lib.workflows.abbreviation_scan_v2.nodes.check_abbreviations import (
    check_abbreviations_node,
)
from lib.workflows.abbreviation_scan_v2.state import AbbreviationScanV2State
from lib.workflows.context import ContextSchema


def build_abbreviation_scan_v2_graph():
    """Build the abbreviation scan v2 workflow graph."""
    graph = StateGraph(AbbreviationScanV2State, context_schema=ContextSchema)

    graph.add_node("check_abbreviations", check_abbreviations_node)
    graph.add_node("apply_ignored_list", apply_ignored_list_node)

    graph.set_entry_point("check_abbreviations")
    graph.add_edge("check_abbreviations", "apply_ignored_list")
    graph.set_finish_point("apply_ignored_list")

    return graph  # type: ignore[return-value]
