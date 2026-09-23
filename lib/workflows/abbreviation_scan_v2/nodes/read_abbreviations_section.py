"""Find and read the Abbreviations section for abbreviation scan v2.

Runs before chunking: the section's lines are kept out of the chunks, and its
entries supply each occurrence's Abbreviations-section definition.
"""

import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.abbreviations_section_extractor import (
    AbbreviationsSectionExtractorAgent,
)
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationsSectionRange,
    LineRange,
)
from lib.workflows.abbreviation_scan_v2.state import AbbreviationScanV2State
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node("Read Abbreviations section")
async def read_abbreviations_section_node(
    state: AbbreviationScanV2State, runtime: Runtime[ContextSchema]
) -> dict:
    main_file = await runtime.context.file_artifacts_service.get_main_file()
    markdown = (main_file.markdown or "") if main_file else ""
    if not markdown.strip():
        return {}

    result, messages = await AbbreviationsSectionExtractorAgent(runtime.context).ainvoke(
        {"markdown": markdown}
    )
    sections = _valid_sections(result.sections, markdown.count("\n") + 1)
    ranges = [LineRange(start_line=s.start_line, end_line=s.end_line) for s in sections]
    # Every reported section stays out of the chunks (the skill never
    # catalogues a glossary's own lines), but a glossary of ordinary terms is
    # not where abbreviations are listed, so only a listing section counts.
    # Both are judged on the sections that survived validation: a listing
    # reported outside the document is not evidence the section exists, so
    # its entries are not trusted as section definitions either.
    entries = result.entries if sections else []
    found = bool(sections) and (
        any(s.lists_abbreviations for s in sections) or bool(entries)
    )

    logger.info(
        f"[AbbreviationScanV2] Abbreviations section found={found}: "
        f"{[(r.start_line, r.end_line) for r in ranges]}, {len(entries)} entries"
    )
    return {
        "abbreviations_section_found": found,
        "abbreviations_section_ranges": ranges,
        "abbreviations_section_entries": entries,
        "messages": messages,
    }


def _valid_sections(
    sections: List[AbbreviationsSectionRange], total_lines: int
) -> List[AbbreviationsSectionRange]:
    """Clamp the agent's line numbers to the document, dropping impossible ranges."""
    valid: List[AbbreviationsSectionRange] = []
    for section in sections:
        start = max(section.start_line, 1)
        end = min(section.end_line, total_lines)
        if start > end:
            logger.warning(
                f"[AbbreviationScanV2] Ignoring section range {section.start_line}-"
                f"{section.end_line} outside a {total_lines}-line document"
            )
            continue
        valid.append(section.model_copy(update={"start_line": start, "end_line": end}))
    return valid
