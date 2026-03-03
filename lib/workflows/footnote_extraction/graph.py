"""Graph definition for footnote extraction workflow."""

from langgraph.graph import StateGraph

from lib.workflows.context import ContextSchema
from lib.workflows.footnote_extraction.nodes.detect_footnotes_section import (
    detect_footnotes_section_node,
)
from lib.workflows.footnote_extraction.nodes.extract_footnotes import (
    extract_footnotes_node,
)
from lib.workflows.footnote_extraction.state import (
    FootnoteExtractionState,
)


def build_footnote_extraction_graph():
    """
    Build footnote extraction workflow graph.

    1. detect_sections - Find footnote sections at document end using pattern matching
    2. extract_footnotes - Extract and parse footnotes with marker, text, reference_code

    Returns FootnoteItem list for independent footnote storage.
    """
    graph = StateGraph(FootnoteExtractionState, context_schema=ContextSchema)

    graph.add_node("detect_sections", detect_footnotes_section_node)
    graph.add_node("extract_footnotes", extract_footnotes_node)

    graph.set_entry_point("detect_sections")
    graph.add_edge("detect_sections", "extract_footnotes")
    graph.set_finish_point("extract_footnotes")

    return graph
