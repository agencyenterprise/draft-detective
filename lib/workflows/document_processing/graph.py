"""Document processing workflow graph."""

from langgraph.graph import END, StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.nodes.convert_to_markdown import (
    convert_to_markdown,
)
from lib.workflows.document_processing.state import DocumentProcessingState


def build_document_processing_graph() -> StateGraph:
    """
    Build a LangGraph workflow for document processing.

    Returns:
        Configured StateGraph for document processing workflow
    """

    graph = StateGraph(DocumentProcessingState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("convert_to_markdown", convert_to_markdown)

    # Entry point
    graph.set_entry_point("convert_to_markdown")

    # Core edges
    graph.add_edge("convert_to_markdown", END)

    return graph  # type: ignore[return-value]
