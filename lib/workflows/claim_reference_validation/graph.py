from langgraph.graph import StateGraph

from lib.workflows.claim_reference_validation.nodes.index_supporting_documents import (
    index_supporting_documents,
)
from lib.workflows.claim_reference_validation.nodes.verify_claims import verify_claims
from lib.workflows.claim_reference_validation.state import ClaimReferenceValidationState
from lib.workflows.context import ContextSchema


def build_claim_reference_validation_graph() -> StateGraph:
    """
    Build a LangGraph workflow for claim reference validation.

    This workflow indexes supporting documents and verifies claims using RAG.

    Returns:
        Configured StateGraph for claim reference validation workflow
    """

    graph = StateGraph(ClaimReferenceValidationState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("index_supporting_documents", index_supporting_documents)
    graph.add_node("verify_claims", verify_claims)

    # Add edges
    graph.set_entry_point("index_supporting_documents")
    graph.add_edge("index_supporting_documents", "verify_claims")
    graph.set_finish_point("verify_claims")

    return graph
