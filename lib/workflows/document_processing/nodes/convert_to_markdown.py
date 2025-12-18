import logging

from lib.config.env import config
from lib.run_utils import run_tasks
from lib.services.converters.base import convert_to_markdown as convert_to_markdown_fn
from lib.services.file import FileDocument
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.decorators import register_node
from langchain_core.messages.utils import count_tokens_approximately

logger = logging.getLogger(__name__)

# We need to limit concurrent docling conversions to avoid overwhelming docling-serve with big documents
# Even 3 can be too many for docling-serve with 4 workers, so we use 2
MAX_CONCURRENT_CONVERSIONS = 2


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
        max_concurrent=MAX_CONCURRENT_CONVERSIONS,
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
    Convert document and capture Docling data if using Docling converter.

    Args:
        file_document: The document to convert
        is_main_document: If True, process with full mode (images, JSON).
                         If False, process with simple mode (markdown only).
    """
    docling_document = None

    if config.FILE_CONVERTER == "docling":
        from lib.services.converters.docling import docling_converter

        simple_mode = not is_main_document
        result = await docling_converter.convert_with_docling(
            file_document.file_path, simple_mode=simple_mode
        )
        markdown = result["markdown"]
        docling_document = result.get("docling_document")
    else:
        markdown = await convert_to_markdown_fn(file_document.file_path)

    markdown_token_count = count_tokens_approximately([markdown])

    return file_document.model_copy(
        update={
            "markdown": markdown,
            "markdown_token_count": markdown_token_count,
            "docling_document": docling_document,
        }
    )

