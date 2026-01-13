import logging
import os
import shutil

from langchain_core.messages.utils import count_tokens_approximately
from langgraph.runtime import Runtime

from lib.config.env import config
from lib.run_utils import run_tasks
from lib.services.converters.base import convert_to_markdown as convert_to_markdown_fn
from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentProcessingState

logger = logging.getLogger(__name__)


@register_node(
    "Convert to markdown",
    "Convert the main and supporting documents to markdown",
)
async def convert_to_markdown(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
) -> DocumentProcessingState:
    # We need to convert only the main document with full mode (images, JSON, etc.), supporting documents with simple mode (markdown only)
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

    failed_errors = [e for e in errors if e is not None]
    if failed_errors:
        error_msg = f"Failed to convert {len(failed_errors)} document(s)"
        logger.error(f"{error_msg}: {failed_errors[0]}")
        raise failed_errors[0]

    [file, *supporting_files] = results
    return {"file": file, "supporting_files": supporting_files}


async def _convert_to_markdown_task(
    file_document: FileDocument, is_main_document: bool = True
) -> FileDocument:
    """
    Route document conversion to the appropriate converter based on configuration.

    Selects either docling or markitdown converter based on config.MAIN_FILE_CONVERTER
    or config.SUPPORTING_FILE_CONVERTER, depending on whether this is the main document.

    Args:
        file_document: The document to convert
        is_main_document: Whether this is the main document

    Returns:
        FileDocument with converted markdown content and metadata
    """
    from lib.services.converters.docling import docling_converter

    converter = (
        config.MAIN_FILE_CONVERTER
        if is_main_document
        else config.SUPPORTING_FILE_CONVERTER
    )

    if converter == "docling":
        return await _convert_to_markdown_using_docling(file_document, is_main_document)
    elif converter == "markitdown":
        return await _convert_to_markdown_using_markitdown(
            file_document, is_main_document
        )
    else:
        raise ValueError(f"Invalid converter: {converter}")


async def _convert_to_markdown_using_markitdown(
    file_document: FileDocument, is_main_document: bool = True
) -> FileDocument:
    """
    Convert document to markdown using markitdown converter.

    Handles legacy .doc files by first converting them to .docx format.
    Calculates token count for the resulting markdown content.

    Args:
        file_document: The document to convert
        is_main_document: Unused parameter (kept for interface consistency)

    Returns:
        FileDocument with markdown content, token count, and docling_document set to None
    """

    file_path = file_document.file_path.lower()
    is_legacy_doc_mime = file_document.file_type == "application/msword"
    is_legacy_doc_extension = file_path.endswith(".doc")

    if is_legacy_doc_mime:
        # If the file is truly a legacy doc format, we need to convert it to docx first
        docx_file_path = await docx_preprocessor.convert_doc_to_docx(file_path)
        logger.info(f"Converted {file_path} to DOCX: {docx_file_path}")
        markdown = await convert_to_markdown_fn(docx_file_path, converter="markitdown")
        os.remove(docx_file_path)  # Remove the temporary docx file
    elif is_legacy_doc_extension:
        # If the file is not a legacy doc format, but has a .doc extension, we need to rename the extension to .docx
        # so markitdown can convert it
        docx_file_path = await _copy_doc_to_docx(file_path)
        logger.info(f"Copied {file_path} to {docx_file_path}")
        markdown = await convert_to_markdown_fn(docx_file_path, converter="markitdown")
        os.remove(docx_file_path)  # Remove the temporary docx file
    else:
        markdown = await convert_to_markdown_fn(file_path, converter="markitdown")

    markdown_token_count = count_tokens_approximately([markdown])

    return file_document.model_copy(
        update={
            "markdown": markdown,
            "markdown_token_count": markdown_token_count,
            "docling_document": None,
        }
    )


async def _convert_to_markdown_using_docling(
    file_document: FileDocument, is_main_document: bool = True
) -> FileDocument:
    """
    Convert document using docling converter with markitdown fallback for markdown extraction.

    First converts the document to markdown using markitdown. Then, for main DOCX/DOC documents,
    also converts to PDF and uses docling to extract structured data (images, tables, etc.).
    For supporting documents or non-DOCX files, uses docling in simple mode.

    Args:
        file_document: The document to convert (should already have markdown from markitdown)
        is_main_document: If True and file is DOCX/DOC, also extract docling_document with full mode.
                         If False, use simple mode for docling conversion.

    Returns:
        FileDocument with markdown content and docling_document (structured data from docling)
    """
    from lib.services.converters.docling import docling_converter

    # Still use markitdown to extract the markdown content from the document
    file_document = await _convert_to_markdown_using_markitdown(
        file_document, is_main_document
    )

    file_path = file_document.file_path
    file_path_lower = file_document.file_path.lower()
    is_docx = file_path_lower.endswith(".docx") or file_path_lower.endswith(".doc")
    docling_document = None
    simple_mode = not is_main_document

    # For main DOCX/DOC documents with docling converter, also convert to PDF
    # to extract docling_document results (images, tables, etc.)
    if is_main_document and is_docx:
        pdf_file_path = await docx_preprocessor.convert_to_pdf(file_path)
        logger.info(
            f"Converted {file_path} to PDF: {pdf_file_path}, extracting docling_document results..."
        )
        result = await docling_converter.convert_with_docling(
            pdf_file_path, simple_mode=False
        )
    else:
        result = await docling_converter.convert_with_docling(
            file_path, simple_mode=simple_mode
        )

    docling_document = result.get("docling_document")

    return file_document.model_copy(
        update={
            "docling_document": docling_document,
        }
    )


async def _copy_doc_to_docx(file_path: str) -> str:
    """
    Copy a .doc file to a .docx file in the same directory.
    """

    docx_file_path = file_path.replace(".doc", ".docx")
    shutil.copy(file_path, docx_file_path)
    return docx_file_path
