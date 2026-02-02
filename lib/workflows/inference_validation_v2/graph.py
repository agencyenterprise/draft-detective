from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.inference_validation_v2.nodes.synthesize_inferences import (
    synthesize_inferences,
)
from lib.workflows.inference_validation_v2.nodes.validate_inferences_v2 import (
    VALIDATOR_NODES,
    prepare_inference_runs,
)
from lib.workflows.inference_validation_v2.state import InferenceValidationV2State


def build_inference_validation_v2_graph() -> StateGraph:
    """Build graph: prepare -> N parallel validator nodes -> synthesize.

    Uses set_entry_point / set_finish_point like other workflows. Parallelization:
    prepare_inference_runs fans out to validate_inference_1..N, all feed into
    synthesize_inferences. N is driven by VALIDATOR_NODES (NUM_VALIDATOR_RUNS).
    """
    graph = StateGraph(InferenceValidationV2State, context_schema=ContextSchema)

    graph.add_node("prepare_inference_runs", prepare_inference_runs)
    for name, node_fn in VALIDATOR_NODES.items():
        graph.add_node(name, node_fn)
    graph.add_node("synthesize_inferences", synthesize_inferences)

    graph.set_entry_point("prepare_inference_runs")
    validator_names = list(VALIDATOR_NODES)
    for name in validator_names:
        graph.add_edge("prepare_inference_runs", name)
    # Single edge from all validators so synthesize runs once after all complete
    graph.add_edge(validator_names, "synthesize_inferences")
    graph.set_finish_point("synthesize_inferences")

    return graph
