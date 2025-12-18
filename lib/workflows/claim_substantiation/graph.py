from langgraph.graph import START, StateGraph

from lib.workflows.claim_substantiation.nodes.categorize_claims import categorize_claims
from lib.workflows.claim_substantiation.nodes.detect_citations import detect_citations
from lib.workflows.claim_substantiation.nodes.extract_claims import extract_claims
from lib.workflows.claim_substantiation.nodes.extract_claims_toulmin import (
    extract_claims_toulmin,
)
from lib.workflows.claim_substantiation.nodes.extract_references import (
    extract_references,
)
from lib.workflows.claim_substantiation.nodes.index_supporting_documents import (
    index_supporting_documents,
)
from lib.workflows.claim_substantiation.nodes.validate_inferences import (
    validate_inferences,
)
from lib.workflows.claim_substantiation.nodes.verify_claims import (
    verify_claims,
    verify_claims_with_rag,
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
    graph.add_node("extract_references", extract_references)

    # We must fan out from START to both extract_references and extract_claims because we need to run both in parallel.
    graph.add_edge(START, "extract_references")
    graph.add_edge(START, "extract_claims")

    # add categorization and inference validation nodes
    graph.add_node("categorize_claims", categorize_claims)
    graph.add_node("validate_inferences", validate_inferences)

    # Conditional verify node based on RAG setting
    if config.use_rag:
        # add RAG indexing node
        graph.add_node("index_supporting_documents", index_supporting_documents)
        graph.add_node("verify_claims", verify_claims_with_rag, defer=True)

        graph.add_edge(START, "index_supporting_documents")
        graph.add_edge("index_supporting_documents", "verify_claims")

    else:
        graph.add_node("verify_claims", verify_claims, defer=True)

    # verify claims edges
    graph.add_edge("extract_claims", "categorize_claims")
    graph.add_edge("categorize_claims", "verify_claims")
    graph.add_edge("detect_citations", "verify_claims")
    graph.add_edge("categorize_claims", "validate_inferences")
    graph.add_edge("extract_references", "detect_citations")

    # Create a finalize node to wait for both verify_claims and validate_inferences to complete in parallel
    graph.add_node("finalize", finalize)
    graph.add_edge("verify_claims", "finalize")
    graph.add_edge("validate_inferences", "finalize")
    graph.set_finish_point("finalize")

    return graph


if __name__ == "__main__":
    # Print the graph in mermaid format
    # Paste it into https://mermaid.live/ to see the graph

    workflow_graph = build_claim_substantiator_graph(
        SubstantiationWorkflowConfig(
            use_rag=True,
        )
    )
    app = workflow_graph.compile()
    print(app.get_graph().draw_mermaid())
