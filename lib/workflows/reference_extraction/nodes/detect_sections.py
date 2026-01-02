"""Node for detecting reference sections in a document."""

import logging

from langgraph.runtime import Runtime

from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_extraction.utils.section_detector import detect_sections

logger = logging.getLogger(__name__)


@register_node(
    "Detect reference sections",
    "Detect reference/bibliography sections in the document",
)
async def detect_sections_node(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """
    Detect reference sections in the document.

    Extracts all markdown headings and uses LLM to identify
    which ones are reference/bibliography sections.

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

    sections = await detect_sections(markdown, runtime.context)

    logger.info(f"Detected {len(sections)} reference section(s)")

    return {"detected_sections": sections}
