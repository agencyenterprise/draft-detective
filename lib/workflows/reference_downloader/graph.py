from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.reference_downloader.nodes.download_references import (
    download_references,
)
from lib.workflows.reference_downloader.nodes.fetch_references import fetch_references
from lib.workflows.reference_downloader.state import ReferenceDownloaderState


def build_reference_downloader_graph():
    graph = StateGraph(ReferenceDownloaderState, context_schema=ContextSchema)

    graph.add_node("fetch_references", fetch_references)
    graph.add_node("download_references", download_references)

    graph.set_entry_point("fetch_references")
    graph.add_edge("fetch_references", "download_references")
    graph.set_finish_point("download_references")

    return graph
