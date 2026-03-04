"""Node for extracting references using LLM with deduplication."""

import logging
import uuid
from difflib import SequenceMatcher
from typing import List

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.reference_text_extractor import ReferenceTextExtractorAgent
from lib.run_utils import run_tasks
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionState,
    ReferenceSection,
)

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
MAX_WINDOW_SIZE = 2000
PREVIOUS_REFS_COUNT = 3
MAX_CONCURRENT_SECTIONS = 10


def _is_duplicate(text: str, existing: List[str]) -> bool:
    """Check if text is similar to any existing reference."""
    for existing_text in existing:
        if (
            SequenceMatcher(None, text.lower(), existing_text.lower()).ratio()
            >= SIMILARITY_THRESHOLD
        ):
            return True
    return False


def _split_into_windows(text: str, max_size: int) -> List[str]:
    """Split text into windows of max_size, breaking at line boundaries."""
    if len(text) <= max_size:
        return [text]

    windows = []
    lines = text.split("\n")
    current_window: List[str] = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > max_size and current_window:
            windows.append("\n".join(current_window))
            current_window = [line]
            current_size = line_size
        else:
            current_window.append(line)
            current_size += line_size

    if current_window:
        windows.append("\n".join(current_window))

    return windows


async def _extract_from_section(
    section: ReferenceSection,
    markdown: str,
    agent: ReferenceTextExtractorAgent,
    config,
) -> List[str]:
    """Extract references from a section using windowed approach."""
    section_text = markdown[section.start_offset : section.end_offset]
    windows = _split_into_windows(section_text, MAX_WINDOW_SIZE)

    if len(windows) > 1:
        logger.info(
            f"Section ({len(section_text)} chars) split into {len(windows)} windows"
        )

    all_refs: List[str] = []

    for i, window in enumerate(windows):
        logger.debug(f"Processing window {i}: {len(window)} chars")

        prev_refs = all_refs[-PREVIOUS_REFS_COUNT:] if all_refs else []
        previous_context = "\n".join(prev_refs) if prev_refs else None

        prompt_kwargs = {"text": window}
        if previous_context:
            prompt_kwargs["previous_context"] = previous_context

        result = await agent.ainvoke(prompt_kwargs, config=config)
        all_refs.extend(result.references)

    return all_refs


@register_node(
    "Extract references",
    "Extract references from detected sections using LLM",
)
async def extract_text_references_node(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """Extract references from detected sections using LLM."""
    main_file = await runtime.context.file_artifacts_service.get_main_file()
    markdown = main_file.markdown
    sections = state.detected_sections

    if not sections:
        logger.info("No reference sections detected")
        return {"extracted_references": []}

    agent = ReferenceTextExtractorAgent(runtime.context)
    config = ensure_config()

    tasks = [_extract_from_section(s, markdown, agent, config) for s in sections]
    results, errors = await run_tasks(
        tasks,
        desc="Extracting references from sections",
        max_concurrent=MAX_CONCURRENT_SECTIONS,
    )

    # Collect unique reference texts first
    unique_texts: List[str] = []
    for section_refs in results:
        if section_refs is not None:
            for ref_text in section_refs:
                if ref_text and not _is_duplicate(ref_text, unique_texts):
                    unique_texts.append(ref_text)

    # Create ExtractedReference objects with unique IDs
    extracted_references = [
        ExtractedReference(id=str(uuid.uuid4()), text=text) for text in unique_texts
    ]

    logger.info(f"Extracted {len(extracted_references)} unique references")
    return {"extracted_references": extracted_references}
