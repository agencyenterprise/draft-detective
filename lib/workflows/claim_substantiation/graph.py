from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.context import ContextSchema


def finalize(state: ClaimSubstantiatorState) -> ClaimSubstantiatorState:
    return {}


def build_claim_substantiator_graph(
    config: SubstantiationWorkflowConfig = SubstantiationWorkflowConfig(),
) -> StateGraph:
    """
    Build a LangGraph workflow for claim substantiation analysis.

    Args:
        config: Configuration for the claim substantiation workflow

    Returns:
        Configured StateGraph for claim substantiation workflow
    """

    graph = StateGraph(ClaimSubstantiatorState, context_schema=ContextSchema)

    # Empty workflow - citations are detected by CITATION_DETECTION workflow
    graph.add_node("finalize", finalize)
    graph.set_entry_point("finalize")
    graph.set_finish_point("finalize")

    return graph


if __name__ == "__main__":
    # Print the graph in mermaid format
    # Paste it into https://mermaid.live/ to see the graph

    workflow_graph = build_claim_substantiator_graph(SubstantiationWorkflowConfig())
    app = workflow_graph.compile()
    print(app.get_graph().draw_mermaid())
