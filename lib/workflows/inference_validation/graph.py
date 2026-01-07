from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.inference_validation.nodes.validate_inferences import (
    validate_inferences,
)
from lib.workflows.inference_validation.state import InferenceValidationState


def build_inference_validation_graph() -> StateGraph:
    graph = StateGraph(InferenceValidationState, context_schema=ContextSchema)

    graph.add_node("validate_inferences", validate_inferences)
    graph.set_entry_point("validate_inferences")
    graph.set_finish_point("validate_inferences")

    return graph
