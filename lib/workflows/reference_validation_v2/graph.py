from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_validation_v2.nodes.reference_validation import (
    distribute_validations,
    finalize_validations,
    initialize_validations,
    validate_single_reference,
)
from lib.workflows.reference_validation_v2.state import ReferenceValidationV2State


def build_reference_validation_v2_graph() -> StateGraph:
    """Build a LangGraph workflow for reference validation v2 with incremental updates."""
    graph = StateGraph(ReferenceValidationV2State, context_schema=ContextSchema)

    graph.add_node("initialize_validations", initialize_validations)
    graph.add_node("distribute_validations", distribute_validations)
    graph.add_node("validate_single_reference", validate_single_reference)
    graph.add_node("finalize_validations", finalize_validations)

    graph.set_entry_point("initialize_validations")
    graph.add_conditional_edges("initialize_validations", distribute_validations)
    graph.add_edge("validate_single_reference", "finalize_validations")
    graph.set_finish_point("finalize_validations")

    return graph  # type: ignore[return-value]
