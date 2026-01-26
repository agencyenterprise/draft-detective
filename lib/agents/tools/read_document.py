"""Read tool for main document content by line range."""

import asyncio

from langchain.tools import ToolRuntime, tool

from lib.workflows.context import ContextSchema

# Maximum lines to read in a single request
MAX_LINES = 200


@tool()
def read_document(
    start_line: int,
    end_line: int,
    runtime: ToolRuntime[ContextSchema],
) -> str:
    """
    Read a specific line range from the main document. The maximum number of lines to read is 200.

    Args:
        start_line: The starting line number (1-indexed, inclusive).
        end_line: The ending line number (1-indexed, inclusive).

    Returns:
        The content of the specified line range with line numbers, with the format "line_number|line_content". Example:
        1|Line 1 content
        2|Line 2 content
        3|Line 3 content
        ...
    """
    return asyncio.run(_read_document_async(start_line, end_line, runtime.context))


async def _read_document_async(
    start_line: int, end_line: int, context: ContextSchema
) -> str:
    """Async implementation of document read."""
    try:
        main_file = await context.file_artifacts_service.get_main_file()
        if not main_file or not main_file.markdown:
            return "Error: Main document not found or has no content."

        markdown = main_file.markdown
        lines = markdown.split("\n")
        total_lines = len(lines)

        # Convert to 0-indexed
        start_idx = max(0, start_line - 1)
        end_idx = min(end_line, total_lines)

        # Validate range
        if start_idx >= total_lines:
            return f"Error: start_line {start_line} is beyond document length ({total_lines} lines)"

        if end_idx <= start_idx:
            return f"Error: end_line must be greater than start_line"

        # Check MAX_LINES limit
        requested_lines = end_idx - start_idx
        if requested_lines > MAX_LINES:
            return f"Error: Requested {requested_lines} lines but maximum is {MAX_LINES} lines per request. Please use a smaller range."

        # Build result
        result_lines = []
        for i in range(start_idx, end_idx):
            line_num = i + 1  # 1-indexed for display
            result_lines.append(f"{line_num}|{lines[i]}")

        header = f"Lines {start_idx + 1}-{end_idx} of {total_lines} total lines\n\n"

        return header + "\n".join(result_lines)

    except Exception as e:
        return f"Error reading document: {str(e)}"
