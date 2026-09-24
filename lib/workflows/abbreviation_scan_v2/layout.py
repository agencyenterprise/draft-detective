"""Chunk boundaries for abbreviation scan v2.

Cuts the document into contiguous line-range chunks small enough for one agent
each. Plain text processing; no model is involved.
"""

import re
from typing import List, Optional

from lib.services.document_sections import split_into_sections
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    ChunkStatus,
    LineRange,
)

# Characters per chunk. Matches the claim-validation splitter, which already
# produces sub-section break points at roughly this size.
CHUNK_CHARS = 8_000

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")


def is_heading_line(line: str) -> bool:
    return _HEADING_RE.match(line) is not None


def build_chunks(markdown: str, section_ranges: List[LineRange]) -> List[AbbreviationChunk]:
    """Cut the document into contiguous chunks that together cover every line.

    Chunks break at the Abbreviations section's boundaries, so a chunk is
    either wholly inside it (and skipped: the section is never catalogued) or
    wholly outside. Blank chunks are skipped too.
    """
    if not markdown.strip():
        return []

    lines = markdown.split("\n")
    chunks: List[AbbreviationChunk] = []
    for start, end in _pack_segments(lines, _break_points(markdown, lines, section_ranges), section_ranges):
        skip_reason = _skip_reason(lines[start - 1 : end], start, section_ranges)
        chunks.append(
            AbbreviationChunk(
                chunk_index=len(chunks),
                start_line=start,
                end_line=end,
                status=ChunkStatus.SKIPPED if skip_reason else ChunkStatus.PENDING,
                skip_reason=skip_reason,
            )
        )
    return chunks


def _skip_reason(
    chunk_lines: List[str], start: int, section_ranges: List[LineRange]
) -> Optional[str]:
    if any(r.contains(start) for r in section_ranges):
        return "abbreviations section"
    if not any(line.strip() for line in chunk_lines):
        return "blank"
    return None


def _break_points(markdown: str, lines: List[str], section_ranges: List[LineRange]) -> List[int]:
    points = {1}
    points.update(s.start_line for s in split_into_sections(markdown))
    points.update(n for n, line in enumerate(lines, start=1) if is_heading_line(line))
    for r in section_ranges:
        points.update((r.start_line, r.end_line + 1))
    return sorted(p for p in points if 1 <= p <= len(lines))


def _pack_segments(
    lines: List[str], breaks: List[int], section_ranges: List[LineRange]
) -> List[tuple[int, int]]:
    """Greedily merge consecutive segments into chunks of at most CHUNK_CHARS.

    A segment never joins across the Abbreviations section's boundary. A single
    segment larger than the budget stays whole: the splitter already cut every
    section down to that size, so only an unbroken run of text is left.
    """

    def in_section(line: int) -> bool:
        return any(r.contains(line) for r in section_ranges)

    segments = list(zip(breaks, [b - 1 for b in breaks[1:]] + [len(lines)]))
    packed: List[tuple[int, int]] = []
    size = 0
    for start, end in segments:
        seg_size = sum(len(line) + 1 for line in lines[start - 1 : end])
        if packed and in_section(packed[-1][0]) == in_section(start) and size + seg_size <= CHUNK_CHARS:
            packed[-1] = (packed[-1][0], end)
            size += seg_size
        else:
            packed.append((start, end))
            size = seg_size
    return packed
