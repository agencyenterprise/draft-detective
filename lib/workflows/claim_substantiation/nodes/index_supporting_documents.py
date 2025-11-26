import logging

from langgraph.runtime import Runtime

from lib.services.file import FileDocument
from lib.services.vector_store import (
    VectorStoreService,
    get_collection_id,
    get_file_hash_from_path,
)
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Index supporting documents",
    "Index supporting documents for RAG retrieval",
)
async def index_supporting_documents(
    state: ClaimSubstantiatorState,
    runtime: Runtime[ContextSchema],
) -> ClaimSubstantiatorState:
    """
    Index supporting documents for RAG retrieval.
    Skips if use_rag is False or no supporting files provided.
    """
    if not state.config.use_rag:
        logger.info("RAG disabled, skipping indexing")
        return {}

    if not state.supporting_files:
        logger.info("No supporting files to index")
        return {}

    logger.info(f"Indexing {len(state.supporting_files)} supporting documents for RAG")

    indexed_count = 0
    failed_files: list[str] = []
    errors: list[WorkflowError] = []

    for file_doc in state.supporting_files:
        try:
            await index_file_document(file_doc, runtime.context.vector_store)
            indexed_count += 1

        except Exception as e:
            logger.error(f"Failed to index {file_doc.file_name}: {e}")
            errors.append(
                WorkflowError(
                    task_name="index_supporting_documents",
                    error=str(e),
                )
            )
            failed_files.append(file_doc.file_name)

    if indexed_count:
        logger.info(f"Successfully indexed {indexed_count} collections")
    if failed_files:
        logger.warning(f"Failed to index {len(failed_files)} files: {failed_files}")

    return {"errors": errors}


async def index_file_document(
    file_doc: FileDocument, vector_store: VectorStoreService
) -> int:
    file_hash = get_file_hash_from_path(file_doc.file_path)
    collection_id = get_collection_id(file_hash)

    collection_exists = await vector_store.is_collection_indexed(collection_id)
    if collection_exists:
        logger.info(f"Collection {collection_id} already exists, skipping indexing")
        return 0

    indexed_docs_count = await vector_store.index_document(
        markdown_content=file_doc.markdown,
        file_name=file_doc.file_name,
        collection_id=collection_id,
    )
    return indexed_docs_count
