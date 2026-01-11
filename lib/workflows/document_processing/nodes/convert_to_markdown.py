import logging

from lib.config.env import config
from lib.run_utils import run_tasks
from lib.services.converters.base import convert_to_markdown as convert_to_markdown_fn
from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.file import FileDocument
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.decorators import register_node
from langchain_core.messages.utils import count_tokens_approximately

logger = logging.getLogger(__name__)


@register_node(
    "Convert to markdown",
    "Convert the main and supporting documents to markdown",
)
async def convert_to_markdown(
    state: DocumentProcessingState,
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
    Convert document using the appropriate converter.

    Args:
        file_document: The document to convert
        is_main_document: If True, use MAIN_FILE_CONVERTER with full mode (images, JSON).
                         If False, use SUPPORTING_FILE_CONVERTER with simple mode (markdown only).
    """
    from lib.services.converters.docling import docling_converter

    converter = (
        config.MAIN_FILE_CONVERTER
        if is_main_document
        else config.SUPPORTING_FILE_CONVERTER
    )

    file_path = file_document.file_path
    file_path_lower = file_document.file_path.lower()
    is_pdf = file_path_lower.endswith(".pdf")
    is_docx = file_path_lower.endswith(".docx") or file_path_lower.endswith(".doc")

    docling_document = None

    # Convert to markdown using appropriate converter
    if converter == "docling" and is_pdf:
        # Use docling for PDF files for improved quality
        simple_mode = not is_main_document
        result = await docling_converter.convert_with_docling(
            file_path, simple_mode=simple_mode
        )
        markdown = result["markdown"]
        docling_document = result.get("docling_document")
    else:
        # Other formats can be converted with markitdown for faster conversion
        markdown = await convert_to_markdown_fn(file_path, converter="markitdown")

    markdown_token_count = count_tokens_approximately([markdown])

    # For main DOCX/DOC documents with docling converter, also convert to PDF
    # to extract docling_document results (images, tables, etc.)
    if is_main_document and converter == "docling" and is_docx:
        pdf_file_path = await docx_preprocessor.convert_to_pdf(file_path)
        logger.info(
            f"Converted {file_path} to PDF: {pdf_file_path}, extracting docling_document results..."
        )
        result = await docling_converter.convert_with_docling(
            pdf_file_path, simple_mode=False
        )
        docling_document = result.get("docling_document")

    return file_document.model_copy(
        update={
            "markdown": markdown,
            "markdown_token_count": markdown_token_count,
            "docling_document": docling_document,
        }
    )
