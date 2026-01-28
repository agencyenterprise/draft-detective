"""Utility for matching line ranges to chunk indices."""

from typing import Any, List, Optional, Protocol, Sequence


class ChunkWithLines(Protocol):
    """Protocol for chunks with line information."""

    chunk_index: int
    start_line: int
    end_line: int


def find_chunks_by_line_range(
    chunks: Sequence[Any],
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
    chunks: Sequence[Any],
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

