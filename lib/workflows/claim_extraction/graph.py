from langgraph.graph import StateGraph

from lib.workflows.claim_extraction.nodes.categorize_claims import categorize_claims
from lib.workflows.claim_extraction.nodes.extract_claims import extract_claims
from lib.workflows.claim_extraction.state import ClaimExtractionState
from lib.workflows.context import ContextSchema


def build_claim_extraction_graph() -> StateGraph:
    """
    Build a LangGraph workflow for claim extraction and categorization.

    Args:
        config: Configuration for the claim extraction workflow

    Returns:
        Configured StateGraph for claim extraction workflow
    """

    graph = StateGraph(ClaimExtractionState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("extract_claims", extract_claims)
    graph.add_node("categorize_claims", categorize_claims)

    # Add edges
    graph.set_entry_point("extract_claims")
    graph.add_edge("extract_claims", "categorize_claims")
    graph.set_finish_point("categorize_claims")

    return graph  # type: ignore[return-value]
