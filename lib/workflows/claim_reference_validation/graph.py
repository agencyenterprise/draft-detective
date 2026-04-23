from langgraph.graph import StateGraph

from lib.workflows.claim_reference_validation.nodes.verify_claims import (
    distribute_verifications,
    finalize_verifications,
    initialize_verifications,
    verify_single_paragraph,
)
from lib.workflows.claim_reference_validation.state import ClaimReferenceValidationState
from lib.workflows.context import ContextSchema


def build_claim_reference_validation_graph():
    """Build a LangGraph workflow for claim reference validation.

    The workflow uses a fan-out pattern to verify claims in parallel.
    Supporting documents are indexed lazily on first vector search.

    1. initialize_verifications: Creates all paragraphs with PENDING status
    2. distribute_verifications: Fans out to parallel verification via Send
    3. verify_single_paragraph: Processes one paragraph (runs in parallel)
    4. finalize_verifications: Flattens results after all verifications complete

    State updates are streamed incrementally as each paragraph completes.
    """
    graph = StateGraph(ClaimReferenceValidationState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("initialize_verifications", initialize_verifications)
    graph.add_node("distribute_verifications", distribute_verifications)
    graph.add_node("verify_single_paragraph", verify_single_paragraph)
    graph.add_node("finalize_verifications", finalize_verifications)

    # Entry point: initialize all paragraphs with PENDING status
    graph.set_entry_point("initialize_verifications")

    # After initialization, distribute to parallel verification operations
    graph.add_conditional_edges("initialize_verifications", distribute_verifications)

    # After all parallel verifications complete, finalize results
    graph.add_edge("verify_single_paragraph", "finalize_verifications")

    # Finish after finalization
    graph.set_finish_point("finalize_verifications")

    return graph  # type: ignore[return-value]
