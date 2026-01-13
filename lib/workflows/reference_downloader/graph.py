from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_downloader.nodes.fetch_references import (
    cleanup_failed_resources,
    distribute_references,
    fetch_single_reference,
    initialize_references,
)
from lib.workflows.reference_downloader.state import ReferenceDownloaderState


def build_reference_downloader_graph():
    """Build a LangGraph workflow for reference downloading with incremental updates.

    The workflow uses a fan-out pattern:
    1. initialize_references: Creates all entries with PENDING status
    2. distribute_references: Fans out to parallel fetch operations via Send
    3. fetch_single_reference: Processes one reference (runs in parallel)
    4. cleanup_failed_resources: Cleans up after all fetches complete

    State updates are streamed incrementally as each reference completes.
    """
    graph = StateGraph(ReferenceDownloaderState, context_schema=ContextSchema)

    # Add nodes
    graph.add_node("initialize_references", initialize_references)
    graph.add_node("distribute_references", distribute_references)
    graph.add_node("fetch_single_reference", fetch_single_reference)
    graph.add_node("cleanup_failed_resources", cleanup_failed_resources)

    # Entry point: initialize all references with PENDING status
    graph.set_entry_point("initialize_references")

    # After initialization, distribute to parallel fetch operations
    graph.add_conditional_edges("initialize_references", distribute_references)

    # distribute_references returns Send objects that invoke fetch_single_reference
    # After all parallel fetches complete, cleanup runs
    graph.add_edge("fetch_single_reference", "cleanup_failed_resources")

    # Finish after cleanup
    graph.set_finish_point("cleanup_failed_resources")

    return graph
