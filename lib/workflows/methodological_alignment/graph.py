from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.methodological_alignment.nodes.align_methodology import (
    align_methodology,
)
from lib.workflows.methodological_alignment.state import MethodologicalAlignmentState


def build_methodological_alignment_graph() -> StateGraph:

    graph = StateGraph(MethodologicalAlignmentState, context_schema=ContextSchema)

    graph.add_node("align_methodology", align_methodology)

    graph.set_entry_point("align_methodology")
    graph.set_finish_point("align_methodology")

    return graph
