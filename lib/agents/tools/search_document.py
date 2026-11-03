"""Grep-like search tool for document content."""

import re

from langchain.tools import ToolRuntime, tool

from lib.workflows.context import ContextSchema

# Maximum number of blocks to return, to avoid token overflow. A block is a run of
# matches whose contexts overlap or touch, so more matched lines than this can be shown.
MAX_MATCHES = 50

# Number of context lines before and after each match
CONTEXT_LINES = 2

# Longer lines in a result, matched or context, are cut to this many characters
MAX_CHARS_PER_MATCH = 500


@tool()
async def search_document(
    file_id: str, pattern: str, runtime: ToolRuntime[ContextSchema]
) -> str:
    """
    Search a document for lines matching a pattern (case-insensitive regex).
    Returns matching lines with surrounding context and line numbers. Returns 2 lines before and after each match as extra context.

    Args:
        file_id: The unique identifier of the document file to search.
        pattern: A regex pattern to search for in the document.

    Returns:
        A string containing matching lines with line numbers and context,
        similar to `grep -n -C 2` output format.

        Example:
            Found 2 matches for pattern: clinical trial

            40-## Methods
            41-
            42:The clinical trial was conducted over 12 weeks.
            43-Participants were randomly assigned to groups.
            44-
            --
            87-reported in previous literature.
            88-
            89:Results from this clinical trial demonstrate
            90-significant improvements in patient outcomes.
            91-
    """
    try:
        file = await runtime.context.file_artifacts_service.get_file_document(file_id)
        if not file or not file.markdown:
            return f"Error: Document with id {file_id} not found or has no content."

        markdown = file.markdown
        return search_content(markdown, pattern)

    except Exception as e:
        return f"Error searching document: {str(e)}"


def search_content(content: str, pattern: str) -> str:
    """Search content for pattern and return formatted results."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    lines = content.split("\n")
    matched = {i for i, line in enumerate(lines) if regex.search(line)}
    if not matched:
        return f"No matches found for pattern: {pattern}"

    blocks = _blocks(sorted(matched), len(lines))[:MAX_MATCHES]
    shown = sum(1 for start, end in blocks for i in range(start, end) if i in matched)

    result_header = f"Found {len(matched)} matches"
    if shown < len(matched):
        result_header += f" (showing the first {shown})"
    result_header += f" for pattern: {pattern}\n\n"

    return result_header + "\n--\n".join(
        _format_block(lines, start, end, matched) for start, end in blocks
    )


def _blocks(match_indices: list[int], total_lines: int) -> list[tuple[int, int]]:
    """Each match's line range with its context, overlapping or adjacent ones merged.

    Merged like ``grep -C``, so no line is printed twice.
    """
    blocks: list[tuple[int, int]] = []
    for i in match_indices:
        start = max(0, i - CONTEXT_LINES)
        end = min(total_lines, i + CONTEXT_LINES + 1)
        if blocks and start <= blocks[-1][1]:
            blocks[-1] = (blocks[-1][0], end)
        else:
            blocks.append((start, end))
    return blocks


def _format_block(lines: list[str], start: int, end: int, matched: set[int]) -> str:
    """One block, as ``line:text`` for matches and ``line-text`` for context."""
    formatted = []
    for i in range(start, end):
        text = lines[i]
        if len(text) > MAX_CHARS_PER_MATCH:
            text = text[:MAX_CHARS_PER_MATCH] + "..."
        separator = ":" if i in matched else "-"
        formatted.append(f"{i + 1}{separator}{text}")
    return "\n".join(formatted)
