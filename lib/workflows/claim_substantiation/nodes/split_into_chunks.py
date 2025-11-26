import logging

from langgraph.runtime import Runtime

from lib.run_utils import call_maybe_async
from lib.services.chunk_to_items_mapper import create_chunk_to_items_mapping
from lib.services.nltk_text_splitter import NLTKTextSplitter
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Split into chunks",
    "Split the main document into chunks",
)
async def split_into_chunks(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    markdown = state.file.markdown

    chunker = NLTKTextSplitter(context=runtime.context)

    # Automatically handle both sync and async chunkers
    docs = await call_maybe_async(chunker.create_documents, [markdown])

    # We need to create the chunk-to-items mapping if Docling data is available
    chunk_to_items = None
    if state.file.docling_document:
        try:
            chunk_to_items = create_chunk_to_items_mapping(
                docs, state.file.docling_document
            )
            logger.info(
                f"split_into_chunks ({state.config.session_id}): "
                f"created mapping for {len(docs)} chunks to Docling items"
            )
        except Exception as e:
            logger.warning(
                f"split_into_chunks ({state.config.session_id}): "
                f"failed to create chunk-to-items mapping: {e}"
            )

    return {
        "chunks": [
            DocumentChunk(
                content=doc.page_content,
                chunk_index=doc.metadata.chunk_index,
                paragraph_index=doc.metadata.paragraph_index,
            )
            for doc in docs
        ],
        "chunk_to_items": chunk_to_items,
    }
