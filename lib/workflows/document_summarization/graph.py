"""Document summarization workflow graph."""

from langgraph.graph import END, StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.document_summarization.nodes.summarize_documents import (
    summarize_documents,
)
from lib.workflows.document_summarization.state import DocumentSummarizationState


def build_document_summarization_graph() -> StateGraph:
    """
    Build a LangGraph workflow for document summarization.

    Returns:
        Configured StateGraph for document summarization workflow
    """

    graph = StateGraph(DocumentSummarizationState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("summarize_documents", summarize_documents)

    # Entry point
    graph.set_entry_point("summarize_documents")

    # Single node workflow
    graph.add_edge("summarize_documents", END)

    return graph  # type: ignore[return-value]
