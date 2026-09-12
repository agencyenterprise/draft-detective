"""Check abbreviations node for abbreviation scan v2 workflow."""

import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.abbreviation_checker import AbbreviationCheckerAgent
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationItem,
    AbbreviationScanV2State,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node("Check abbreviations")
async def check_abbreviations_node(
    state: AbbreviationScanV2State, runtime: Runtime[ContextSchema]
) -> dict:
    agent = AbbreviationCheckerAgent(runtime.context)

    # The catalogue comes back from the `record_abbreviations` tool rather than
    # the terminal response, so a long document's occurrences are not capped by
    # what one structured response can carry.
    output, abbreviations, messages = await agent.ainvoke({})

    distinct: List[str] = sorted({item.abbr for item in abbreviations})

    logger.info(
        f"[AbbreviationScanV2] Recorded {len(abbreviations)} abbreviation occurrences "
        f"across {len(distinct)} distinct abbreviations, "
        f"abbreviations_section_found={output.abbreviations_section_found}"
    )
    if not abbreviations:
        logger.warning(
            "[AbbreviationScanV2] The agent recorded no occurrences through "
            "record_abbreviations; no issues will be reported for this run."
        )

    return {
        "abbreviations": abbreviations,
        "abbreviations_section_found": output.abbreviations_section_found,
        "reasoning": output.reasoning,
        "messages": messages,
    }
