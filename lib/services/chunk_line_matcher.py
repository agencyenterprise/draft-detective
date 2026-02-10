"""Utility for matching line ranges to chunk indices."""

from typing import List, Optional, Protocol, Sequence

from rapidfuzz import fuzz

from nltk.tokenize import sent_tokenize

MIN_LENGTH = 5
MIN_SCORE = 50


class IndexedChunkWithLines(Protocol):
    """Protocol for indexed chunks with line information."""

    chunk_index: int
    start_line: int
    end_line: int


class ChunkWithContent(Protocol):
    """Protocol for chunks with content for fuzzy matching."""

    chunk_index: int
    start_line: int
    end_line: int
    content: str


def find_chunks_by_line_range(
    chunks: Sequence[IndexedChunkWithLines],
    start_line: int,
    end_line: int,
) -> List[int]:
    """
    Find chunk indices that overlap with the given line range.

    Two ranges overlap if: chunk.start_line <= end_line AND chunk.end_line >= start_line

    Args:
        chunks: List of chunks with line information
        start_line: Start of the target line range (1-indexed)
        end_line: End of the target line range (1-indexed)

    Returns:
        List of chunk_index values that overlap with the line range, sorted by chunk_index
    """
    matching = [
        chunk.chunk_index
        for chunk in chunks
        if chunk.start_line <= end_line and chunk.end_line >= start_line
    ]
    return sorted(matching)


def find_chunk_by_line(
    chunks: Sequence[IndexedChunkWithLines],
    line: int,
) -> Optional[int]:
    """
    Find the chunk index containing a specific line.

    Args:
        chunks: List of chunks with line information
        line: The 1-indexed line number to find

    Returns:
        The first matching chunk index, or None if not found
    """
    for chunk in chunks:
        if chunk.start_line <= line <= chunk.end_line:
            return chunk.chunk_index
    return None


def find_chunk_by_fuzzy_match(
    chunks: Sequence[ChunkWithContent],
    input_text: str,
    start_line: Optional[int] = None,
) -> Optional[int]:
    """
    Find the chunk whose content best matches input_text using fuzzy matching.

    Uses rapidfuzz partial_ratio to compare input_text against each chunk's content.
    When multiple chunks have the same best score, selects the one whose start_line
    is closest to the given start_line (if provided); otherwise returns the first
    such chunk by chunk_index order.

    Args:
        chunks: List of chunks with content and line information
        input_text: The text to find (e.g. a key sentence)
        start_line: Optional 1-indexed line hint for tie-breaking

    Returns:
        The chunk_index of the best-matching chunk, or None if chunks is empty
        or input_text is empty
    """
    if not chunks or not input_text.strip():
        return None

    input_text = input_text.strip()
    best_score = -1.0
    best_matches: List[ChunkWithContent] = []

    for chunk in chunks:
        if not chunk.content:
            continue
        score = fuzz.partial_ratio(input_text, chunk.content, score_cutoff=MIN_SCORE)
        if score > best_score:
            best_score = score
            best_matches = [chunk]
        elif score == best_score:
            best_matches.append(chunk)

    if not best_matches:
        return None

    if len(best_matches) == 1:
        return best_matches[0].chunk_index

    if start_line is not None:
        best_matches.sort(
            key=lambda c: abs(c.start_line - start_line),
        )
    else:
        best_matches.sort(key=lambda c: c.chunk_index)

    return best_matches[0].chunk_index


def find_chunks_by_fuzzy_match(
    chunks: Sequence[ChunkWithContent],
    input_text: str,
    start_line: Optional[int] = None,
) -> List[int]:
    if not chunks or not input_text.strip():
        return []

    sentences = sent_tokenize(input_text.strip())

    chunk_indices: List[int] = []
    prev_end_line: Optional[int] = start_line  # for continuity tie-break

    for sentence in sentences:
        idx = find_chunk_by_fuzzy_match(
            chunks, sentence, start_line=prev_end_line  # or None
        )
        if idx is not None:
            chunk_indices.append(idx)
            # Optional: set prev_end_line from matched chunk for next iteration

    return sorted(set(chunk_indices))  # dedupe + sort by chunk_index
