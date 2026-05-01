import logging

from langgraph.runtime import Runtime

from lib.run_utils import run_tasks
from lib.services.file import FileDocument
from lib.services.files import update_file_artifacts
from lib.services.markdown_conversion import convert_file_document_to_markdown
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentProcessingState

logger = logging.getLogger(__name__)


@register_node("Convert to markdown")
async def convert_to_markdown(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
):
    tasks = [
        _convert_to_markdown_task(state.file, is_main_document=True),
        *[
            _convert_to_markdown_task(file, is_main_document=False)
            for file in state.supporting_files or []
        ],
    ]

    results, errors = await run_tasks(
        tasks,
        desc="Converting documents",
        max_concurrent=10,
    )
    files: list[FileDocument] = [file for file in results if file is not None]

    failed_errors = [e for e in errors if e is not None]
    if failed_errors:
        error_msg = f"Failed to convert {len(failed_errors)} document(s)"
        logger.error(f"{error_msg}: {failed_errors[0]}")
        raise failed_errors[0]

    [file, *supporting_files] = files

    # Persist markdown artifacts to database for caching
    await _persist_markdown_artifacts(files)

    return {"file": file, "supporting_files": supporting_files}


async def _persist_markdown_artifacts(files: list[FileDocument]) -> None:
    """
    Persist markdown artifacts to the files table for all converted documents.

    Args:
        file: The main document with markdown content
        supporting_files: List of supporting documents with markdown content
    """

    for file in files:
        await update_file_artifacts(file_id=file.file_id, markdown=file.markdown)


async def _convert_to_markdown_task(
    file_document: FileDocument, is_main_document: bool = True
) -> FileDocument:
    """
    Convert document to markdown.

    Args:
        file_document: The document to convert
        is_main_document: Whether this is the main document (unused, kept for interface consistency)

    Returns:
        FileDocument with converted markdown content and metadata
    """
    return await convert_file_document_to_markdown(file_document)
