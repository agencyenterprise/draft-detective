"""Utility for splitting a markdown document into sections for parallel processing."""

import re
from typing import List, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

from lib.agents.document_chunker_nltk import find_text_line_range


class DocumentSection(BaseModel):
    section_index: int
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    headings: List[str] = Field(default_factory=list)


_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)")

# Target chunk size for the recursive fallback splitter (characters).
# RecursiveCharacterTextSplitter tries \n\n → \n → space → char in order,
# so it handles both well-structured markdown and PDF-converted text where
# paragraphs are broken across many short lines.
_CHUNK_SIZE = 8_000


def _parse_heading_boundaries(lines: List[str]) -> List[Tuple[int, List[str]]]:
    """Return (1-indexed line number, headings hierarchy) for each heading line."""
    current: dict[int, str] = {}
    boundaries: List[Tuple[int, List[str]]] = []
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            current[level] = m.group(2).strip()
            for deeper in range(level + 1, 5):
                current.pop(deeper, None)
            boundaries.append((i + 1, [current[l] for l in sorted(current)]))
    return boundaries


def _subsplit(
    text: str,
    full_markdown: str,
    search_start: int,
    headings: List[str],
    start_index: int,
) -> Tuple[List[DocumentSection], int]:
    """Split a text block with RecursiveCharacterTextSplitter and map back to line numbers."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=0)
    chunks = splitter.split_text(text)

    sections: List[DocumentSection] = []
    pos = search_start
    for chunk in chunks:
        if not chunk.strip():
            continue
        start_line, end_line, pos = find_text_line_range(full_markdown, chunk.strip(), pos)
        sections.append(
            DocumentSection(
                section_index=start_index + len(sections),
                start_line=start_line,
                end_line=end_line,
                headings=headings,
            )
        )
    return sections, pos


def split_into_sections(markdown: str) -> List[DocumentSection]:
    """Split markdown into parallel-processable sections.

    Two-pass strategy:
    1. Regex scan for H1-H4 headings to find section boundaries and extract the
       heading hierarchy. Sections that fit within _CHUNK_SIZE chars are kept as-is.
    2. Sections that exceed _CHUNK_SIZE are fed through RecursiveCharacterTextSplitter
       (character-based, no overlap). The recursive splitter tries \\n\\n → \\n →
       space → char in order, handling both well-structured markdown and
       PDF-converted text where paragraphs are broken into many short lines.
    """
    if not markdown.strip():
        return []

    lines = markdown.split("\n")
    total_lines = len(lines)
    boundaries = _parse_heading_boundaries(lines)

    if not boundaries:
        fallback_sections, _ = _subsplit(markdown, markdown, 0, [], 0)
        return fallback_sections or [DocumentSection(section_index=0, start_line=1, end_line=total_lines)]

    # Build raw sections: each heading starts a section that runs until the next heading.
    raw: List[Tuple[int, int, List[str]]] = []
    first_heading_line = boundaries[0][0]
    if first_heading_line > 1:
        raw.append((1, first_heading_line - 1, []))

    for idx, (start_line, headings) in enumerate(boundaries):
        end_line = boundaries[idx + 1][0] - 1 if idx + 1 < len(boundaries) else total_lines
        raw.append((start_line, end_line, headings))

    # Build sections, subsplitting any block that exceeds _CHUNK_SIZE chars.
    sections: List[DocumentSection] = []
    search_pos = 0

    for start_line, end_line, headings in raw:
        block = "\n".join(lines[start_line - 1 : end_line])

        if len(block) <= _CHUNK_SIZE:
            start_line_found, end_line_found, search_pos = find_text_line_range(
                markdown, block.strip(), search_pos
            )
            sections.append(
                DocumentSection(
                    section_index=len(sections),
                    start_line=start_line_found,
                    end_line=end_line_found,
                    headings=headings,
                )
            )
        else:
            sub, search_pos = _subsplit(block, markdown, search_pos, headings, len(sections))
            sections.extend(sub)

    if not sections:
        return [DocumentSection(section_index=0, start_line=1, end_line=total_lines)]

    for i, s in enumerate(sections):
        s.section_index = i

    return sections
