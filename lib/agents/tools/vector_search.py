"""Vector search tool for claim verification agent."""

import logging
from typing import List

from langchain.tools import ToolRuntime, tool

from lib.services.vector_store import (
    RetrievedPassage,
    get_collection_id,
    get_file_hash_from_path,
)
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

# Number of context lines before and after each matched passage line
CONTEXT_LINES = 2


@tool()
async def vector_search(
    file_id: str,
    query: str,
    top_k: int,
    runtime: ToolRuntime[ContextSchema],
) -> str:
    """
    Search a supporting document for passages relevant to a query using semantic vector search.

    Use this tool to retrieve evidence from supporting documents when verifying claims.
    You must provide the file_id of the supporting document (from the citation-to-file mapping)
    and a search query describing what evidence you are looking for.

    Args:
        file_id: The ID of the supporting file to search (from the citation-to-file mapping).
        query: A natural language query describing the evidence to search for.
        top_k: Maximum number of passages to retrieve (recommended: 10).

    Returns:
        Matched passages with line numbers and surrounding context from the document,
        in a format similar to `grep -n -C 2` output. Each matched chunk line is
        prefixed with its line number followed by `:` (e.g. `42:matched content`),
        while surrounding context lines use `-` (e.g. `40-context line`).
        Non-contiguous blocks are separated by `--`.

        Example:
            Showing 2 most similar passages in 'study.pdf'

            40-## Methods
            41-
            42:The clinical trial was conducted over 12 weeks.
            43:Participants were randomly assigned to groups.
            44:Each group received different treatment protocols.
            45-
            46-Data was collected weekly.
            --
            87-reported in previous literature.
            88-
            89:Results from this clinical trial demonstrate
            90:significant improvements in patient outcomes.
            91:The primary endpoint was met with p < 0.05.
            92-
            93-Further studies are recommended.
    """
    if top_k > 50 or top_k < 1:
        return "Error: top_k must be between 1 and 50."

    try:
        vector_store = runtime.context.vector_store
        if not vector_store:
            return "Error: Vector store is not available."

        supporting_files = (
            await runtime.context.file_artifacts_service.get_supporting_files()
        )
        file_doc = next((f for f in supporting_files if f.file_id == file_id), None)
        if not file_doc:
            return f"Error: No supporting file found with file_id '{file_id}'."

        collection_id = get_collection_id(get_file_hash_from_path(file_doc.file_path))

        # Ensure the file is indexed before searching (lazy indexing with lock)
        await vector_store.ensure_collection_indexed(
            collection_id=collection_id,
            markdown_content=file_doc.markdown,
            file_name=file_doc.file_name,
        )

        passages = await vector_store.retrieve_relevant_passages(
            query=query, collection_id=collection_id, top_k=top_k
        )

        logger.info(
            f"vector_search retrieved {len(passages)} passages from '{file_doc.file_name}' "
            f"(file_id={file_id}) for query: '{query}'"
        )

        if not passages:
            return f"No relevant passages found in '{file_doc.file_name}'."

        formatted_passages = format_passages_with_lines(
            passages, file_doc.markdown, file_doc.file_name
        )

        logger.debug(f"formatted_passages: \n\n{formatted_passages}\n\n")

        return formatted_passages

    except Exception as e:
        logger.error(f"vector_search failed for file_id={file_id}: {e}")
        return f"Error during vector search: {str(e)}"


def format_passages_with_lines(
    passages: List[RetrievedPassage],
    markdown_content: str,
    file_name: str,
) -> str:
    """Format retrieved passages as line-numbered content from the original document.

    Uses the same convention as search_document: `line_number:` for matched
    (chunk) lines and `line_number-` for context lines, with `--` separators
    between non-contiguous blocks.
    """
    lines = markdown_content.split("\n")
    total_lines = len(lines)

    # Collect all matched line indices (0-indexed) from chunk ranges
    matched_line_indices: set[int] = set()
    for p in passages:
        for i in range(p.start_line - 1, p.end_line):  # convert to 0-indexed
            matched_line_indices.add(i)

    # Build expanded ranges (with context) for each chunk
    ranges: List[tuple[int, int]] = []
    for p in passages:
        start = max(0, p.start_line - 1 - CONTEXT_LINES)
        end = min(total_lines, p.end_line + CONTEXT_LINES)
        ranges.append((start, end))

    # Sort and merge overlapping / adjacent ranges
    ranges.sort()
    merged: List[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Format each block
    blocks: List[str] = []
    for start, end in merged:
        block_lines: List[str] = []
        for i in range(start, end):
            line_num = i + 1  # 1-indexed for display
            separator = ":" if i in matched_line_indices else "-"
            block_lines.append(f"{line_num}{separator}{lines[i]}")
        blocks.append("\n".join(block_lines))

    header = f"Showing {len(passages)} most similar passages in '{file_name}'\n\n"
    return header + "\n--\n".join(blocks)
