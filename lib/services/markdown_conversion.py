"""Convert files to markdown and persist them as cached DB artifacts.

Used by any workflow that needs the cached `File.markdown` column populated —
either as part of normal document processing, or after introducing new files
mid-pipeline (e.g. files downloaded by `reference_downloader`).
"""

import logging
import os
import shutil

from langchain_core.messages.utils import count_tokens_approximately

from lib.models.file import FileRole
from lib.services.converters.base import convert_to_markdown as convert_to_markdown_fn
from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.file import FileDocument
from lib.services.files import (
    get_file_by_id,
    load_file_document,
    update_file_artifacts,
)

logger = logging.getLogger(__name__)


def _converter_for(file_path: str, role: FileRole) -> str:
    """Pick the converter backend based on file role and extension.

    The main document goes through markitdown for higher-fidelity output
    (tables, headings, etc.) since downstream agents depend on that
    structure. Supporting PDFs go through pypdfium2 — text-only but with
    a near-flat memory profile, which is what we need to convert academic
    reference batches without OOMing the worker. Non-PDF supporting files
    fall back to markitdown so .docx / .html / .csv etc. still work.
    """
    if role == FileRole.MAIN:
        return "markitdown"
    if file_path.lower().endswith(".pdf"):
        return "pypdfium"
    return "markitdown"


async def convert_file_document_to_markdown(
    file_document: FileDocument,
    role: FileRole = FileRole.MAIN,
) -> FileDocument:
    """Return a copy of ``file_document`` with its markdown content populated.

    Handles legacy ``.doc`` files by first converting them to ``.docx``. If
    the document already has markdown set, returns it unchanged.

    The converter backend is chosen from the file's role: see
    ``_converter_for``. Legacy .doc/.docx files always go through
    markitdown regardless of role (pypdfium is PDF-only).
    """
    if file_document.markdown:
        logger.info(
            f"Using cached markdown for file {file_document.file_name} ({file_document.file_id})"
        )
        return file_document

    file_path = file_document.file_path.lower()
    is_legacy_doc_mime = file_document.file_type == "application/msword"
    is_legacy_doc_extension = file_path.endswith(".doc")

    if is_legacy_doc_mime:
        docx_file_path = await docx_preprocessor.convert_doc_to_docx(file_path)
        logger.info(f"Converted {file_path} to DOCX: {docx_file_path}")
        markdown = await convert_to_markdown_fn(docx_file_path, converter="markitdown")
        os.remove(docx_file_path)
    elif is_legacy_doc_extension:
        docx_file_path = file_path.replace(".doc", ".docx")
        shutil.copy(file_path, docx_file_path)
        logger.info(f"Copied {file_path} to {docx_file_path}")
        markdown = await convert_to_markdown_fn(docx_file_path, converter="markitdown")
        os.remove(docx_file_path)
    else:
        markdown = await convert_to_markdown_fn(
            file_path, converter=_converter_for(file_path, role)
        )

    return file_document.model_copy(
        update={
            "markdown": markdown,
            "markdown_token_count": count_tokens_approximately([markdown]),
        }
    )


async def convert_and_cache_file_markdown(file_id: str) -> None:
    """Convert a file to markdown (if not already cached) and persist to DB.

    Loads the file by id, runs markdown conversion when ``has_cached_markdown``
    is False, and writes the result back via ``update_file_artifacts`` so
    consumers reading via ``file_artifacts_service.get_supporting_files()``
    take the live-DB path instead of the stale ``DocumentProcessingState``
    fallback.
    """
    file = await get_file_by_id(file_id)
    if file.has_cached_markdown:
        return

    file_document = await load_file_document(file, use_cached_artifacts=False)
    # Files entering here come from reference_downloader (always supporting),
    # so route through the pypdfium path for PDFs.
    converted = await convert_file_document_to_markdown(
        file_document, role=FileRole.SUPPORT
    )
    if not converted.markdown:
        logger.warning(
            "Markdown conversion produced empty content for file %s; skipping cache write",
            file_id,
        )
        return

    await update_file_artifacts(file_id=file_id, markdown=converted.markdown)
