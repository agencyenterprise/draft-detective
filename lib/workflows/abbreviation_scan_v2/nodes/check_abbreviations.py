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


@register_node(
    "Check abbreviations",
    "Scan the full document for abbreviation inline definition and Abbreviations section coverage",
)
async def check_abbreviations_node(
    state: AbbreviationScanV2State, runtime: Runtime[ContextSchema]
) -> dict:
    agent = AbbreviationCheckerAgent(runtime.context)

    output, messages = await agent.ainvoke({})

    abbreviations: List[AbbreviationItem] = output.abbreviations

    logger.info(
        f"[AbbreviationScanV2] Found {len(abbreviations)} abbreviation occurrences, "
        f"abbreviations_section_found={output.abbreviations_section_found}"
    )

    return {
        "abbreviations": abbreviations,
        "abbreviations_section_found": output.abbreviations_section_found,
    }
