"""Grep-like search tool for main document content."""

import asyncio
import re
from typing import List

from langchain.tools import ToolRuntime, tool

from lib.workflows.context import ContextSchema

# Maximum number of matches to return to avoid token overflow
MAX_MATCHES = 50

# Number of context lines before and after each match
CONTEXT_LINES = 2

# Maximum characters per match result
MAX_CHARS_PER_MATCH = 500


@tool()
def search_document(pattern: str, runtime: ToolRuntime[ContextSchema]) -> str:
    """
    Search the main document for lines matching a pattern (case-insensitive regex).
    Returns matching lines with surrounding context and line numbers.

    Args:
        pattern: A regex pattern to search for in the document.

    Returns:
        A string containing matching lines with line numbers and context,
        similar to grep -n -C output format.
    """
    return asyncio.run(_search_document_async(pattern, runtime.context))


async def _search_document_async(pattern: str, context: ContextSchema) -> str:
    """Async implementation of document search."""
    try:
        main_file = await context.file_artifacts_service.get_main_file()
        if not main_file or not main_file.markdown:
            return "Error: Main document not found or has no content."

        markdown = main_file.markdown
        return _search_content(markdown, pattern)

    except Exception as e:
        return f"Error searching document: {str(e)}"


def _search_content(content: str, pattern: str) -> str:
    """Search content for pattern and return formatted results."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    lines = content.split("\n")
    matches: List[str] = []
    matched_line_indices = set()

    # Find all matching lines
    for i, line in enumerate(lines):
        if regex.search(line):
            matched_line_indices.add(i)

    if not matched_line_indices:
        return f"No matches found for pattern: {pattern}"

    # Build results with context
    processed_ranges = set()

    for match_idx in sorted(matched_line_indices):
        if match_idx in processed_ranges:
            continue

        start = max(0, match_idx - CONTEXT_LINES)
        end = min(len(lines), match_idx + CONTEXT_LINES + 1)

        # Mark this range as processed
        for i in range(start, end):
            processed_ranges.add(i)

        # Build the match block
        match_block = []
        for i in range(start, end):
            line_num = i + 1  # 1-indexed line numbers
            line_content = lines[i]

            # Truncate long lines
            if len(line_content) > MAX_CHARS_PER_MATCH:
                line_content = line_content[:MAX_CHARS_PER_MATCH] + "..."

            # Mark matching lines with ":" and context lines with "-"
            separator = ":" if i in matched_line_indices else "-"
            match_block.append(f"{line_num}{separator}{line_content}")

        matches.append("\n".join(match_block))

        if len(matches) >= MAX_MATCHES:
            break

    result_header = f"Found {len(matched_line_indices)} matches"
    if len(matched_line_indices) > MAX_MATCHES:
        result_header += f" (showing first {MAX_MATCHES})"
    result_header += f" for pattern: {pattern}\n\n"

    return result_header + "\n--\n".join(matches)
