"""Node for detecting footnote sections in a document."""

import logging

from langgraph.runtime import Runtime

from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.footnote_extraction.state import FootnoteExtractionState
from lib.workflows.footnote_extraction.utils.section_detector import (
    detect_footnote_region,
)

logger = logging.getLogger(__name__)


@register_node(
    "Detect footnote sections",
    "Detect footnote sections at the end of the document using pattern matching",
)
async def detect_sections_node(
    state: FootnoteExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """
    Detect footnote sections in the document.

    Uses pattern-based detection to find numbered footnote entries at document end.
    No LLM needed - scans backwards for patterns like "1.", "[1]", "^1".

    Args:
        state: Current workflow state with file.markdown
        runtime: LangGraph runtime context

    Returns:
        Dict with detected_sections list
    """
    markdown = state.file.markdown

    if not markdown:
        logger.warning("No markdown content in document")
        return {"detected_sections": []}

    sections = detect_footnote_region(markdown)

    logger.info(f"Detected {len(sections)} footnote section(s)")

    return {"detected_sections": sections}
