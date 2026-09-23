"""Combine per-chunk extractions into the document-wide occurrence catalogue.

Each chunk's agent answers only for its own lines, so the fields that depend
on the whole document are computed here: occurrence numbers are counted in document order,
the Abbreviations-section definition is looked up from the section's entries,
and a heading line is always treated as exempt.
"""

import html
import logging
import re
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set, Tuple

from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    AbbreviationSectionEntry,
    ChunkOccurrence,
    LineRange,
)
from lib.workflows.abbreviation_scan_v2.layout import is_heading_line
from lib.workflows.abbreviation_scan_v2.state import AbbreviationItem

logger = logging.getLogger(__name__)

_HEADING_REASON = "Appears in a heading."
_FALLBACK_REASON = "Excluded as an exempt occurrence."
_NON_ALNUM_RE = re.compile(r"[^0-9A-Za-z]")


def assemble_catalogue(
    chunks: List[AbbreviationChunk],
    section_entries: List[AbbreviationSectionEntry],
    section_ranges: List[LineRange],
    lines: List[str],
) -> List[AbbreviationItem]:
    """Build the ordered, numbered catalogue from every chunk that produced results."""
    recorded = [
        occurrence
        for chunk in chunks
        if chunk.produced_results
        for occurrence in chunk.occurrences
        if occurrence.abbr.strip()
        and _inside_chunk(occurrence, chunk)
        and _appears_on_its_lines(occurrence, lines)
        # The skill excludes the Abbreviations section itself.
        and not any(r.contains(occurrence.line_start) for r in section_ranges)
    ]
    recorded = _within_text_count(recorded, lines)
    # Stable: occurrences on the same line keep the agent's reading order.
    recorded.sort(key=lambda occurrence: occurrence.line_start)

    definitions = _section_definitions(section_entries)
    canonical = _canonicalizer({occ.abbr.strip() for occ in recorded} | set(definitions))

    counts: Dict[str, int] = defaultdict(int)
    catalogue: List[AbbreviationItem] = []
    for occ in recorded:
        abbr = canonical(occ.abbr.strip())
        counts[abbr] += 1
        ignored, reason = _exemption(occ, lines)
        catalogue.append(
            AbbreviationItem(
                abbr=abbr,
                inline_definition=occ.inline_definition.strip(),
                occurrence_number=counts[abbr],
                line_start=occ.line_start,
                line_end=max(occ.line_end, occ.line_start),
                abbreviations_section_definition=_lookup(definitions, abbr),
                ignored=ignored,
                ignored_reason=reason,
            )
        )
    return catalogue


def _inside_chunk(occurrence: ChunkOccurrence, chunk: AbbreviationChunk) -> bool:
    """Keep only occurrences on the chunk's own lines.

    An agent may read around its range for context. Anything it records out
    there belongs to a neighbouring chunk, whose agent records it too, so
    keeping it would count the occurrence twice.
    """
    if chunk.start_line <= occurrence.line_start <= chunk.end_line:
        return True
    logger.warning(
        f"[AbbreviationScanV2] Dropped {occurrence.abbr!r} at line {occurrence.line_start}, "
        f"outside chunk {chunk.chunk_index} ({chunk.start_line}-{chunk.end_line})."
    )
    return False


def _appears_on_its_lines(occurrence: ChunkOccurrence, lines: List[str]) -> bool:
    """Reject an occurrence whose abbreviation is not on the lines it names.

    The model occasionally reports an abbreviation on a line that does not
    contain it (typically a nearby heading). HTML entities are decoded (the
    converted markdown writes "R&amp;D"), and punctuation and spacing are
    ignored so "Ph.D." still matches "PhD" and a plural matches its singular.
    """
    needle = _normalized(occurrence.abbr)
    end = max(occurrence.line_end, occurrence.line_start)
    text = _normalized(" ".join(lines[occurrence.line_start - 1 : end]))
    if needle and needle in text:
        return True
    logger.warning(
        f"[AbbreviationScanV2] Dropped {occurrence.abbr!r} reported at lines "
        f"{occurrence.line_start}-{occurrence.line_end}, which do not contain it."
    )
    return False


def _within_text_count(
    occurrences: List[ChunkOccurrence], lines: List[str]
) -> List[ChunkOccurrence]:
    """Cap each abbreviation's entries on a line range at how often its text appears there.

    The model occasionally records the same occurrence twice, e.g. counting the
    spelled-out "Escherichia coli" as a second "E. coli" on the same line.
    Entries beyond the number of times the abbreviation actually appears in the
    text are dropped, keeping the first ones in reading order.
    """
    kept: List[ChunkOccurrence] = []
    seen: Dict[Tuple[int, int, str], int] = defaultdict(int)
    for occurrence in occurrences:
        end = max(occurrence.line_end, occurrence.line_start)
        needle = _normalized(occurrence.abbr)
        key = (occurrence.line_start, end, needle)
        available = _normalized(" ".join(lines[occurrence.line_start - 1 : end])).count(needle)
        if seen[key] < max(available, 1):
            seen[key] += 1
            kept.append(occurrence)
        else:
            logger.warning(
                f"[AbbreviationScanV2] Dropped a repeated {occurrence.abbr!r} at lines "
                f"{occurrence.line_start}-{end}: the text contains it only {available} time(s)."
            )
    return kept


def _normalized(text: str) -> str:
    return _NON_ALNUM_RE.sub("", html.unescape(text))


def _exemption(
    occurrence: ChunkOccurrence, lines: List[str]
) -> Tuple[bool, Optional[str]]:
    """Keep the agent's exemption, and enforce the heading rule it sometimes misses."""
    reason = (occurrence.ignored_reason or "").strip() or None
    if occurrence.ignored:
        return True, reason or _FALLBACK_REASON
    line = lines[occurrence.line_start - 1] if occurrence.line_start <= len(lines) else ""
    if is_heading_line(line):
        return True, _HEADING_REASON
    return False, None


def _section_definitions(entries: List[AbbreviationSectionEntry]) -> Dict[str, str]:
    definitions: Dict[str, str] = {}
    for entry in entries:
        abbr, definition = entry.abbr.strip(), entry.definition.strip()
        if abbr and definition:
            definitions.setdefault(abbr, definition)
    return definitions


def _lookup(definitions: Dict[str, str], abbr: str) -> Optional[str]:
    """Section definition for `abbr`, accepting a section that lists the plural."""
    return definitions.get(abbr) or definitions.get(f"{abbr}s")


def _canonicalizer(known: Set[str]) -> Callable[[str], str]:
    """Fold a plural onto its singular when the singular is also in use.

    Each chunk is told to record the singular base form, but they run
    independently: one chunk writing "LLMs" where the rest wrote "LLM" would
    otherwise count as a separate abbreviation and be flagged as undefined.
    """

    def canonical(abbr: str) -> str:
        singular = abbr[:-1]
        if abbr.endswith("s") and len(singular) >= 2 and singular in known:
            return singular
        return abbr

    return canonical
