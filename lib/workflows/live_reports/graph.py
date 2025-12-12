from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.live_reports.nodes.generate_addendum_report import (
    generate_addendum_report,
)
from lib.workflows.live_reports.nodes.generate_live_reports import (
    generate_live_reports_analysis,
)
from lib.workflows.live_reports.state import LiveReportsState


def build_live_reports_graph() -> StateGraph:
    graph = StateGraph(LiveReportsState, context_schema=ContextSchema)

    graph.add_node("generate_live_reports_analysis", generate_live_reports_analysis)
    graph.add_node("generate_addendum_report", generate_addendum_report)

    graph.set_entry_point("generate_live_reports_analysis")
    graph.add_edge("generate_live_reports_analysis", "generate_addendum_report")
    graph.set_finish_point("generate_addendum_report")

    return graph
