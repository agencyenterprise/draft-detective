"""Apply hardcoded ignored-abbreviations list node for abbreviation scan v2 workflow."""

import logging

from langgraph.runtime import Runtime

from lib.workflows.abbreviation_scan_v2.state import AbbreviationScanV2State
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)

# Abbreviations that should always be excluded from compliance checks regardless
# of how or where they appear in the document.
_IGNORED_ABBREVIATIONS: frozenset[str] = frozenset(
    [
        "RAND",
    ]
)


@register_node(
    "Apply ignored abbreviations list",
    "Mark occurrences of known non-abbreviation terms as ignored",
)
async def apply_ignored_list_node(
    state: AbbreviationScanV2State, runtime: Runtime[ContextSchema]
) -> dict:
    updated = [
        (
            item.model_copy(
                update={
                    "ignored": True,
                    "ignored_reason": f'"{item.abbr}" is in the hardcoded ignored abbreviations list.',
                }
            )
            if item.abbr in _IGNORED_ABBREVIATIONS and not item.ignored
            else item
        )
        for item in state.abbreviations
    ]

    marked = sum(
        1
        for orig, upd in zip(state.abbreviations, updated)
        if orig.ignored != upd.ignored
    )
    if marked:
        logger.info(
            f"[AbbreviationScanV2] Marked {marked} occurrence(s) as ignored "
            f"via hardcoded list: {_IGNORED_ABBREVIATIONS & {i.abbr for i in state.abbreviations}}"
        )

    return {"abbreviations": updated}
