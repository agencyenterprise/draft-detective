"""Grep-like search tool for main document content."""

from langchain.tools import ToolRuntime, tool

from lib.agents.tools.search_document import search_content
from lib.workflows.context import ContextSchema


@tool()
async def search_document(pattern: str, runtime: ToolRuntime[ContextSchema]) -> str:
    """
    Search the main document for lines matching a pattern (case-insensitive regex).
    Returns matching lines with surrounding context and line numbers. Returns 2 lines before and after each match as extra context.

    Args:
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
        main_file = await runtime.context.file_artifacts_service.get_main_file()
        if not main_file or not main_file.markdown:
            return "Error: Main document not found or has no content."

        markdown = main_file.markdown
        return search_content(markdown, pattern)

    except Exception as e:
        return f"Error searching document: {str(e)}"
