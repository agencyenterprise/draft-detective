from langgraph.graph import END, StateGraph

from lib.workflows.abbreviation_scan.nodes.scan_abbreviations import (
    scan_abbreviations_node,
)
from lib.workflows.abbreviation_scan.state import AbbreviationScanState
from lib.workflows.context import ContextSchema


def build_abbreviation_scan_graph() -> StateGraph:
    graph = StateGraph(AbbreviationScanState, context_schema=ContextSchema)
    graph.add_node("scan_abbreviations", scan_abbreviations_node)
    graph.set_entry_point("scan_abbreviations")
    graph.add_edge("scan_abbreviations", END)
    return graph
