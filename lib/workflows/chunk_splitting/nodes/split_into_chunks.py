"""Node for splitting document into chunks."""

import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.document_chunker_nltk import (
    DocumentChunkerAgent,
    get_chunker_result_as_langchain_documents,
)
from lib.agents.models import ValidatedDocument
from lib.services.chunk_to_items_mapper import create_chunk_to_items_mapping
from lib.workflows.chunk_splitting.state import ChunkSplittingState, DocumentChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Split into chunks",
    "Split the main document into chunks",
)
async def split_into_chunks(
    state: ChunkSplittingState, runtime: Runtime[ContextSchema]
):
    if state.chunks:
        logger.info("Using cached chunks for main file")
        return {"chunks": state.chunks, "chunk_to_items": state.chunk_to_items}

    # Get the file document from the file artifacts service
    file_artifacts_service = runtime.context.file_artifacts_service
    file_document = await file_artifacts_service.get_file_document(state.file_id)

    markdown = file_document.markdown

    chunker = DocumentChunkerAgent(context=runtime.context)
    result = await chunker.ainvoke(prompt_kwargs={"full_document": markdown})
    docs: List[ValidatedDocument] = get_chunker_result_as_langchain_documents(result)

    # We need to create the chunk-to-items mapping if Docling data is available
    chunk_to_items = None
    if file_document.docling_document:
        try:
            chunk_to_items = create_chunk_to_items_mapping(
                docs, file_document.docling_document
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
    """Convert a ValidatedDocument to a DocumentChunk."""
    return DocumentChunk(
        content=doc.page_content,
        chunk_index=doc.metadata.chunk_index,
        paragraph_index=doc.metadata.paragraph_index,
        headings=doc.metadata.headings,
    )


def convert_validate_documents_to_chunks(
    docs: List[ValidatedDocument],
) -> List[DocumentChunk]:
    """Convert a list of ValidatedDocuments to a list of DocumentChunks."""
    return [convert_validate_document_to_chunk(doc) for doc in docs]
