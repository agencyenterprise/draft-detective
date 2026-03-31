import logging
import os
import shutil

from langchain_core.messages.utils import count_tokens_approximately
from langgraph.runtime import Runtime

from lib.run_utils import run_tasks
from lib.services.converters.base import convert_to_markdown as convert_to_markdown_fn
from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.services.files import update_file_artifacts

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

    if file_document.markdown:
        logger.info(
            f"Using cached markdown for file {file_document.file_name} ({file_document.file_id})"
        )
        return file_document

    return await _convert_to_markdown_using_markitdown(file_document)


async def _convert_to_markdown_using_markitdown(
    file_document: FileDocument,
) -> FileDocument:
    """
    Convert document to markdown using markitdown converter.

    Handles legacy .doc files by first converting them to .docx format.
    Calculates token count for the resulting markdown content.

    Args:
        file_document: The document to convert

    Returns:
        FileDocument with markdown content and token count
    """

    file_path = file_document.file_path.lower()
    is_legacy_doc_mime = file_document.file_type == "application/msword"
    is_legacy_doc_extension = file_path.endswith(".doc")

    if is_legacy_doc_mime:
        docx_file_path = await docx_preprocessor.convert_doc_to_docx(file_path)
        logger.info(f"Converted {file_path} to DOCX: {docx_file_path}")
        markdown = await convert_to_markdown_fn(docx_file_path, converter="markitdown")
        os.remove(docx_file_path)
    elif is_legacy_doc_extension:
        docx_file_path = await _copy_doc_to_docx(file_path)
        logger.info(f"Copied {file_path} to {docx_file_path}")
        markdown = await convert_to_markdown_fn(docx_file_path, converter="markitdown")
        os.remove(docx_file_path)
    else:
        markdown = await convert_to_markdown_fn(file_path, converter="markitdown")

    markdown_token_count = count_tokens_approximately([markdown])

    return file_document.model_copy(
        update={
            "markdown": markdown,
            "markdown_token_count": markdown_token_count,
        }
    )


async def _copy_doc_to_docx(file_path: str) -> str:
    """
    Copy a .doc file to a .docx file in the same directory.
    """

    docx_file_path = file_path.replace(".doc", ".docx")
    shutil.copy(file_path, docx_file_path)
    return docx_file_path
