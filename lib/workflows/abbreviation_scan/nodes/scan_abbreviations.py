import logging
import re
from typing import Dict, Iterable, List

from langgraph.runtime import Runtime

from lib.workflows.abbreviation_scan.state import (
    AbbreviationItem,
    AbbreviationScanState,
)
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)

_DEFINITION_PATTERN = re.compile(r"([A-Za-z][A-Za-z\s\-,.]+)\s+\(([A-Z0-9]{2,})\)")
_ACRONYM_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]{1,})\b")


def is_reference_section_chunk(chunk: AnalyzedChunk) -> bool:
    if not chunk.headings:
        return False
    haystack = " / ".join(chunk.headings).lower()
    return "reference" in haystack or "bibliography" in haystack


def extract_abbreviations_from_chunks(
    chunks: Iterable[AnalyzedChunk],
) -> List[AbbreviationItem]:
    """Extract abbreviations from chunks based on REGEX patterns."""
    raw_items: List[AbbreviationItem] = []
    definition_map: Dict[str, str] = {}

    for chunk in chunks:
        text = chunk.content or ""
        if not text.strip():
            continue
        if is_reference_section_chunk(chunk):
            continue

        for match in _DEFINITION_PATTERN.finditer(text):
            definition = match.group(1).strip()
            abbr = match.group(2).strip()

            if len(abbr) >= 2:
                definition_map[abbr] = definition
                raw_items.append(
                    AbbreviationItem(
                        abbr=abbr,
                        definition=definition,
                        context=text,
                        is_definition=True,
                        chunk_index=chunk.chunk_index,
                    )
                )

        for match in _ACRONYM_PATTERN.finditer(text):
            abbr = match.group(1)

            if len(abbr) < 2:
                continue
            if any(i.abbr == abbr and i.is_definition for i in raw_items):
                continue

            raw_items.append(
                AbbreviationItem(
                    abbr=abbr,
                    definition=definition_map.get(abbr, ""),
                    context=text,
                    is_definition=False,
                    chunk_index=chunk.chunk_index,
                )
            )

    unique: List[AbbreviationItem] = []
    seen: set[str] = set()

    for item in [i for i in raw_items if i.is_definition]:
        if item.abbr not in seen:
            unique.append(item)
            seen.add(item.abbr)

    for item in [i for i in raw_items if not i.is_definition]:
        if item.abbr in seen:
            continue

        definition = definition_map.get(item.abbr)
        if definition:
            item = item.model_copy(update={"definition": definition})

        unique.append(item)
        seen.add(item.abbr)

    return unique


@register_node(
    "Scan abbreviations",
    "Scan document for abbreviations, acronyms, and definition pairs",
)
async def scan_abbreviations_node(
    state: AbbreviationScanState, runtime: Runtime[ContextSchema]
) -> dict:
    file_artifacts_service = runtime.context.file_artifacts_service

    chunks = await file_artifacts_service.get_chunks()

    abbreviations: List[AbbreviationItem] = []

    try:
        abbreviations = extract_abbreviations_from_chunks(chunks)
    except Exception as e:
        logger.error(f"Abbreviation scan failed: {e}", exc_info=True)
        abbreviations = []

    return {"abbreviations": abbreviations}
