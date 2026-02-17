"""Read tool for main document content by line range."""

from langchain.tools import ToolRuntime, tool

from lib.agents.tools.read_document import read_content
from lib.workflows.context import ContextSchema


@tool()
async def read_document(
    start_line: int,
    end_line: int,
    runtime: ToolRuntime[ContextSchema],
) -> str:
    """
    Read a specific line range from the main document. The maximum number of lines to read is 300.

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
    try:
        main_file = await runtime.context.file_artifacts_service.get_main_file()
        if not main_file or not main_file.markdown:
            return "Error: Main document not found or has no content."

        return read_content(main_file.markdown, start_line, end_line)

    except Exception as e:
        return f"Error reading document: {str(e)}"
