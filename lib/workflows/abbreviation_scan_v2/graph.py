"""Graph definition for abbreviation scan v2 workflow."""

from langgraph.graph import StateGraph

from lib.workflows.abbreviation_scan_v2.nodes.apply_ignored_list import (
    apply_ignored_list_node,
)
from lib.workflows.abbreviation_scan_v2.nodes.assemble_catalogue import (
    assemble_catalogue_node,
)
from lib.workflows.abbreviation_scan_v2.nodes.extract_chunks import (
    distribute_chunks,
    extract_chunk_node,
    prepare_chunks_node,
)
from lib.workflows.abbreviation_scan_v2.nodes.read_abbreviations_section import (
    read_abbreviations_section_node,
)
from lib.workflows.abbreviation_scan_v2.state import AbbreviationScanV2State
from lib.workflows.context import ContextSchema


def build_abbreviation_scan_v2_graph():
    """Build the abbreviation scan v2 workflow graph.

    1. read_abbreviations_section: locate the section and read its entries
    2. prepare_chunks: cut the rest of the document into line-range chunks
    3. extract_chunk: catalogue one chunk (fanned out via Send, in parallel)
    4. assemble_catalogue: number occurrences document-wide, attach section
       definitions, report failed chunks as warnings
    5. apply_ignored_list: exclude the hardcoded always-ignored abbreviations
    """
    graph = StateGraph(AbbreviationScanV2State, context_schema=ContextSchema)

    graph.add_node("read_abbreviations_section", read_abbreviations_section_node)
    graph.add_node("prepare_chunks", prepare_chunks_node)
    graph.add_node("extract_chunk", extract_chunk_node)
    graph.add_node("assemble_catalogue", assemble_catalogue_node)
    graph.add_node("apply_ignored_list", apply_ignored_list_node)

    graph.set_entry_point("read_abbreviations_section")
    graph.add_edge("read_abbreviations_section", "prepare_chunks")
    graph.add_conditional_edges(
        "prepare_chunks", distribute_chunks, ["extract_chunk", "assemble_catalogue"]
    )
    graph.add_edge("extract_chunk", "assemble_catalogue")
    graph.add_edge("assemble_catalogue", "apply_ignored_list")
    graph.set_finish_point("apply_ignored_list")

    return graph  # type: ignore[return-value]
