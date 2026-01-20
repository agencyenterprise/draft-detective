import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.models import ValidatedDocument
from lib.run_utils import call_maybe_async
from lib.services.chunk_to_items_mapper import create_chunk_to_items_mapping
from lib.services.nltk_text_splitter import NLTKTextSplitter
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import (
    DocumentChunk,
    DocumentProcessingState,
)

logger = logging.getLogger(__name__)


@register_node(
    "Split into chunks",
    "Split the main document into chunks",
)
async def split_into_chunks(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
):
    markdown = state.file.markdown

    chunker = NLTKTextSplitter(context=runtime.context)

    # Automatically handle both sync and async chunkers
    docs: List[ValidatedDocument] = await call_maybe_async(
        chunker.create_documents, [markdown]
    )

    # We need to create the chunk-to-items mapping if Docling data is available
    chunk_to_items = None
    if state.file.docling_document:
        try:
            chunk_to_items = create_chunk_to_items_mapping(
                docs, state.file.docling_document
            )
            logger.info(
                f"split_into_chunks: created mapping for {len(docs)} chunks to Docling items"
            )
        except Exception as e:
            logger.warning(
                f"split_into_chunks: failed to create chunk-to-items mapping: {e}"
            )

    return {
        "chunks": convert_validate_documents_to_chunks(docs),
        "chunk_to_items": chunk_to_items,
    }


def convert_validate_document_to_chunk(doc: ValidatedDocument) -> DocumentChunk:
    """
    Convert a ValidatedDocument to a DocumentChunk.
    """

    return DocumentChunk(
        content=doc.page_content,
        chunk_index=doc.metadata.chunk_index,
        paragraph_index=doc.metadata.paragraph_index,
        headings=doc.metadata.headings,
    )


def convert_validate_documents_to_chunks(
    docs: List[ValidatedDocument],
) -> List[DocumentChunk]:
    """
    Convert a list of ValidatedDocuments to a list of DocumentChunks.
    """

    return [convert_validate_document_to_chunk(doc) for doc in docs]
