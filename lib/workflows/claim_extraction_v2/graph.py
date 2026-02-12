from langgraph.graph import StateGraph

from lib.workflows.claim_extraction_v2.nodes.extract_claims_v2 import (
    extract_claims_v2,
)
from lib.workflows.claim_extraction_v2.state import ClaimExtractionV2State
from lib.workflows.context import ContextSchema


def build_claim_extraction_v2_graph() -> StateGraph:
    """Build a LangGraph workflow for claim extraction v2.

    Single-node graph: extract_claims_v2 (paragraph-group based extraction).
    No categorization node.
    """

    graph = StateGraph(ClaimExtractionV2State, context_schema=ContextSchema)

    graph.add_node("extract_claims_v2", extract_claims_v2)

    graph.set_entry_point("extract_claims_v2")
    graph.set_finish_point("extract_claims_v2")

    return graph  # type: ignore[return-value]
