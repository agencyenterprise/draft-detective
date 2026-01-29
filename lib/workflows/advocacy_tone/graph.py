from langgraph.graph import StateGraph

from lib.workflows.advocacy_tone.nodes.detect_advocacy_tone import detect_advocacy_tone
from lib.workflows.advocacy_tone.state import AdvocacyToneState
from lib.workflows.context import ContextSchema


def build_advocacy_tone_graph() -> StateGraph:
    """Build the advocacy and tone detection workflow graph."""
    graph = StateGraph(AdvocacyToneState, context_schema=ContextSchema)

    graph.add_node("detect_advocacy_tone", detect_advocacy_tone)
    graph.set_entry_point("detect_advocacy_tone")
    graph.set_finish_point("detect_advocacy_tone")

    return graph

