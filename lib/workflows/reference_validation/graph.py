from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_validation.nodes.reference_validation import (
    reference_validation,
)
from lib.workflows.reference_validation.state import ReferenceValidationState


def build_reference_validation_graph() -> StateGraph:
    graph = StateGraph(ReferenceValidationState, context_schema=ContextSchema)

    graph.add_node("reference_validation", reference_validation)
    graph.set_entry_point("reference_validation")
    graph.set_finish_point("reference_validation")

    return graph
