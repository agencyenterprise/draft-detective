"""Node for extracting footnotes using LLM."""

import logging
from typing import List

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.footnote_extractor import FootnoteExtractorAgent
from lib.models.footnote_item import FootnoteItem
from lib.run_utils import run_tasks
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.footnote_extraction.state import (
    FootnoteExtractionState,
    FootnoteSection,
)

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SECTIONS = 10


async def _extract_from_section(
    section: FootnoteSection,
    markdown: str,
    agent: FootnoteExtractorAgent,
    config,
) -> List[FootnoteItem]:
    """Extract footnotes from a section."""
    section_text = markdown[section.start_offset : section.end_offset]

    logger.debug(f"Processing section: {len(section_text)} chars")

    result = await agent.ainvoke({"text": section_text}, config=config)
    return result.footnotes


@register_node(
    "Extract footnotes",
    "Extract structured footnotes from detected sections using LLM",
)
async def extract_footnotes_node(
    state: FootnoteExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """Extract footnotes from detected sections using LLM."""
    markdown = state.file.markdown
    sections = state.detected_sections

    if not sections:
        logger.info("No footnote sections detected")
        return {"footnotes": []}

    agent = FootnoteExtractorAgent(runtime.context)
    config = ensure_config()

    tasks = [_extract_from_section(s, markdown, agent, config) for s in sections]
    results, errors = await run_tasks(
        tasks,
        desc="Extracting footnotes from sections",
        max_concurrent=MAX_CONCURRENT_SECTIONS,
    )

    footnotes: List[FootnoteItem] = []
    for section_footnotes in results:
        if section_footnotes is not None:
            footnotes.extend(section_footnotes)

    logger.info(f"Extracted {len(footnotes)} footnotes")
    return {"footnotes": footnotes}
