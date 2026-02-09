from langgraph.graph import StateGraph

from lib.workflows.claim_reference_validation_v2.nodes.execute import execute
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2State,
)
from lib.workflows.context import ContextSchema


def build_claim_reference_validation_v2_graph() -> StateGraph:
    """Build a LangGraph workflow for claim reference validation v2."""
    graph = StateGraph(ClaimReferenceValidationV2State, context_schema=ContextSchema)

    # Add node
    graph.add_node("execute", execute)

    # Define flow
    graph.set_entry_point("execute")
    graph.set_finish_point("execute")

    return graph
