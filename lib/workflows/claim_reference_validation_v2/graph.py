"""LangGraph workflow graph for Claim Reference Validation V2."""

from langgraph.graph import StateGraph

from lib.workflows.claim_reference_validation_v2.nodes.validate_sections import (
    distribute_sections,
    finalize_results,
    prepare_sections,
    validate_section,
)
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2State,
)
from lib.workflows.context import ContextSchema


def build_claim_reference_validation_v2_graph():
    """Build the Claim Reference Validation V2 LangGraph workflow.

    Fan-out pattern:
    1. prepare_sections: Split document into sections, create PENDING items
    2. distribute_sections: Fan out via Send, one per section
    3. validate_section: Agent validates citations in one section (runs in parallel)
    4. finalize_results: Flatten all section issues
    """
    graph = StateGraph(ClaimReferenceValidationV2State, context_schema=ContextSchema)

    graph.add_node("prepare_sections", prepare_sections)
    graph.add_node("distribute_sections", distribute_sections)
    graph.add_node("validate_section", validate_section)
    graph.add_node("finalize_results", finalize_results)

    graph.set_entry_point("prepare_sections")
    graph.add_conditional_edges("prepare_sections", distribute_sections)
    graph.add_edge("validate_section", "finalize_results")
    graph.set_finish_point("finalize_results")

    return graph
