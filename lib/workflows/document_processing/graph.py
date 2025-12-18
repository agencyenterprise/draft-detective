"""Document processing workflow graph."""

from langgraph.graph import StateGraph, END

from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.nodes.convert_to_markdown import (
    convert_to_markdown,
)
from lib.workflows.document_processing.nodes.prepare_documents import prepare_documents
from lib.workflows.document_processing.nodes.split_into_chunks import split_into_chunks
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)


def build_document_processing_graph(
    config: DocumentProcessingWorkflowConfig = DocumentProcessingWorkflowConfig(),
) -> StateGraph:
    """
    Build a LangGraph workflow for document processing.

    Args:
        config: Configuration for the document processing workflow

    Returns:
        Configured StateGraph for document processing workflow
    """

    graph = StateGraph(DocumentProcessingState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("convert_to_markdown", convert_to_markdown)
    graph.add_node("prepare_documents", prepare_documents)
    graph.add_node("split_into_chunks", split_into_chunks)

    # Entry point
    graph.set_entry_point("convert_to_markdown")

    # Core edges - main processing pipeline
    graph.add_edge("convert_to_markdown", "prepare_documents")
    graph.add_edge("prepare_documents", "split_into_chunks")
    graph.add_edge("split_into_chunks", END)

    return graph
