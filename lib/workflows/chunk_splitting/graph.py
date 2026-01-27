"""Chunk splitting workflow graph."""

from langgraph.graph import END, StateGraph

from lib.workflows.chunk_splitting.nodes.split_into_chunks import split_into_chunks
from lib.workflows.chunk_splitting.state import ChunkSplittingState
from lib.workflows.context import ContextSchema


def build_chunk_splitting_graph() -> StateGraph:
    """
    Build a LangGraph workflow for chunk splitting.

    Returns:
        Configured StateGraph for chunk splitting workflow
    """

    graph = StateGraph(ChunkSplittingState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("split_into_chunks", split_into_chunks)

    # Entry point
    graph.set_entry_point("split_into_chunks")

    # Core edges
    graph.add_edge("split_into_chunks", END)

    return graph
