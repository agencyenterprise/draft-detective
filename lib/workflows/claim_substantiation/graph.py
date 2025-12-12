from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.nodes.categorize_claims import categorize_claims
from lib.workflows.claim_substantiation.nodes.convert_to_markdown import (
    convert_to_markdown,
)
from lib.workflows.claim_substantiation.nodes.detect_citations import detect_citations
from lib.workflows.claim_substantiation.nodes.extract_claims import extract_claims
from lib.workflows.claim_substantiation.nodes.extract_claims_toulmin import (
    extract_claims_toulmin,
)
from lib.workflows.claim_substantiation.nodes.extract_references import (
    extract_references,
)
from lib.workflows.claim_substantiation.nodes.generate_addendum_report import (
    generate_addendum_report,
)
from lib.workflows.claim_substantiation.nodes.generate_live_reports import (
    generate_live_reports_analysis,
)
from lib.workflows.claim_substantiation.nodes.index_supporting_documents import (
    index_supporting_documents,
)
from lib.workflows.claim_substantiation.nodes.prepare_documents import prepare_documents
from lib.workflows.claim_substantiation.nodes.split_into_chunks import split_into_chunks
from lib.workflows.claim_substantiation.nodes.suggest_citations import suggest_citations
from lib.workflows.claim_substantiation.nodes.summarize_supporting_documents import (
    summarize_supporting_documents,
)
from lib.workflows.claim_substantiation.nodes.validate_inferences import (
    validate_inferences,
)
from lib.workflows.claim_substantiation.nodes.validate_references import (
    validate_references,
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
    graph.add_node("convert_to_markdown", convert_to_markdown)
    graph.add_node("prepare_documents", prepare_documents)
    graph.add_node("split_into_chunks", split_into_chunks)
    graph.add_node(
        "extract_claims",
        extract_claims if not config.use_toulmin else extract_claims_toulmin,
    )
    graph.add_node("detect_citations", detect_citations)
    graph.add_node("extract_references", extract_references)

    # Optional nodes
    if config.run_reference_validation:
        graph.add_node("validate_references", validate_references)
    if config.run_suggest_citations:
        graph.add_node("summarize_supporting_documents", summarize_supporting_documents)
        graph.add_node("suggest_citations", suggest_citations, defer=True)
    if config.run_live_reports:
        graph.add_node(
            "generate_live_reports_analysis", generate_live_reports_analysis, defer=True
        )
        graph.add_node("generate_addendum_report", generate_addendum_report, defer=True)

    # Entry point
    graph.set_entry_point("convert_to_markdown")

    # Core edges - main processing pipeline
    graph.add_edge("convert_to_markdown", "prepare_documents")
    graph.add_edge("prepare_documents", "split_into_chunks")
    graph.add_edge("split_into_chunks", "extract_references")
    graph.add_edge("split_into_chunks", "extract_claims")

    # Live reports edges
    if config.run_live_reports:
        graph.add_edge("extract_references", "generate_live_reports_analysis")
        graph.add_edge("extract_claims", "generate_live_reports_analysis")
        graph.add_edge("generate_live_reports_analysis", "generate_addendum_report")
        graph.set_finish_point("generate_addendum_report")

    # Peer review edges
    else:
        # add categorization and inference validation nodes
        graph.add_node("categorize_claims", categorize_claims)
        graph.add_node("validate_inferences", validate_inferences)

        # Conditional verify node based on RAG setting
        if config.use_rag:
            # add RAG indexing node
            graph.add_node("index_supporting_documents", index_supporting_documents)
            graph.add_node("verify_claims", verify_claims_with_rag, defer=True)

            graph.add_edge("prepare_documents", "index_supporting_documents")
            graph.add_edge("index_supporting_documents", "verify_claims")

        else:
            graph.add_node("verify_claims", verify_claims, defer=True)

        # verify claims edges
        graph.add_edge("extract_claims", "categorize_claims")
        graph.add_edge("categorize_claims", "verify_claims")
        graph.add_edge("detect_citations", "verify_claims")
        graph.add_edge("categorize_claims", "validate_inferences")

        if config.run_reference_validation:
            graph.add_edge("extract_references", "validate_references")
            graph.add_edge("validate_references", "detect_citations")
        else:
            graph.add_edge("extract_references", "detect_citations")

        # Suggest citations (aim 2.a)
        # Must wait for ALL processing to complete before suggesting citations
        if config.run_suggest_citations:
            graph.add_edge("prepare_documents", "summarize_supporting_documents")
            graph.add_edge("verify_claims", "suggest_citations")
            graph.add_edge("validate_inferences", "suggest_citations")
            graph.add_edge("summarize_supporting_documents", "suggest_citations")
            graph.set_finish_point("suggest_citations")
        else:
            # When no downstream nodes exist, create a finalize node to wait for both
            # verify_claims and validate_inferences to complete in parallel
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
            run_live_reports=True,
            run_reference_validation=True,
            run_suggest_citations=True,
            use_rag=True,
        )
    )
    app = workflow_graph.compile()
    print(app.get_graph().draw_mermaid())
