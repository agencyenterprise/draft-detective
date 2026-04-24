from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_validation.nodes.reference_validation import (
    distribute_validations,
    finalize_validations,
    initialize_validations,
    validate_single_reference,
)
from lib.workflows.reference_validation.state import ReferenceValidationState


def build_reference_validation_graph() -> StateGraph:
    """Build a LangGraph workflow for reference validation with incremental updates.

    The workflow uses a fan-out pattern:
    1. initialize_validations: Creates all entries with PENDING status
    2. distribute_validations: Fans out to parallel validation operations via Send
    3. validate_single_reference: Processes one reference (runs in parallel)
    4. finalize_validations: Finalizes after all validations complete

    State updates are streamed incrementally as each reference completes.
    """
    graph = StateGraph(ReferenceValidationState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("initialize_validations", initialize_validations)
    graph.add_node("distribute_validations", distribute_validations)
    graph.add_node("validate_single_reference", validate_single_reference)
    graph.add_node("finalize_validations", finalize_validations)

    # Entry point: initialize all validations with PENDING status
    graph.set_entry_point("initialize_validations")

    # After initialization, distribute to parallel validation operations
    graph.add_conditional_edges("initialize_validations", distribute_validations)

    # distribute_validations returns Send objects that invoke validate_single_reference
    # After all parallel validations complete, finalize runs
    graph.add_edge("validate_single_reference", "finalize_validations")

    # Finish after finalization
    graph.set_finish_point("finalize_validations")

    return graph  # type: ignore[return-value]
