from langgraph.graph import START, StateGraph

from lib.workflows.claim_substantiation.nodes.categorize_claims import categorize_claims
from lib.workflows.claim_substantiation.nodes.detect_citations import detect_citations
from lib.workflows.claim_substantiation.nodes.extract_claims import extract_claims
from lib.workflows.claim_substantiation.nodes.extract_claims_toulmin import (
    extract_claims_toulmin,
)
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

    # Core nodes
    graph.add_node(
        "extract_claims",
        extract_claims if not config.use_toulmin else extract_claims_toulmin,
    )
    graph.add_node("detect_citations", detect_citations)

    # Fan out from START to run extract_claims and detect_citations in parallel
    # Note: references are pre-extracted by REFERENCE_EXTRACTION workflow
    graph.add_edge(START, "extract_claims")
    graph.add_edge(START, "detect_citations")

    # add categorization node
    graph.add_node("categorize_claims", categorize_claims)

    # Core edges
    graph.add_edge("extract_claims", "categorize_claims")
    graph.add_edge("detect_citations", "categorize_claims")

    # Create a finalize node to wait for categorize_claims to complete
    graph.add_node("finalize", finalize)
    graph.add_edge("categorize_claims", "finalize")
    graph.set_finish_point("finalize")

    return graph


if __name__ == "__main__":
    # Print the graph in mermaid format
    # Paste it into https://mermaid.live/ to see the graph

    workflow_graph = build_claim_substantiator_graph(SubstantiationWorkflowConfig())
    app = workflow_graph.compile()
    print(app.get_graph().draw_mermaid())
