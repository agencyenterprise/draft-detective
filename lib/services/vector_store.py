import asyncio
import logging
import os
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine

from lib.config.llm_models import init_embeddings

logger = logging.getLogger(__name__)


# Semantic chunking settings
CHUNK_SIZE = 800  # Target characters per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks for context continuity

# Batching settings for OpenAI embedding API
EMBEDDING_BATCH_SIZE = 100

# Markdown-aware text splitter: splits on headings, paragraphs, sentences, then chars.
# add_start_index=True makes create_documents() emit a "start_index" metadata field
# with the character offset of each chunk in the original text, which we use to
# compute accurate line ranges even when duplicate text appears in the document.
_splitter = RecursiveCharacterTextSplitter.from_language(
    Language.MARKDOWN,
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    add_start_index=True,
)


class RetrievedPassage(BaseModel):
    """Represents a passage retrieved from vector store."""

    content: str = Field(description="The text content of the retrieved passage")
    source_file: str = Field(description="Name of the source file")
    start_line: int = Field(description="1-indexed start line of the chunk")
    end_line: int = Field(description="1-indexed end line of the chunk")
    cosine_distance: float = Field(
        description="Cosine distance (0-1, lower = more similar)"
    )


def _char_offset_to_line(text: str, char_offset: int) -> int:
    """Convert a character offset to a 1-indexed line number."""
    return text[:char_offset].count("\n") + 1


def _char_offset_to_line_range(
    text: str, char_offset: int, chunk_text: str
) -> Tuple[int, int]:
    """Convert a character offset and chunk text to a (start_line, end_line) tuple.

    Args:
        text: The full document text.
        char_offset: The character offset where the chunk starts in the document.
        chunk_text: The chunk text (used to compute end_line).

    Returns:
        Tuple of (start_line, end_line), both 1-indexed.
    """
    start_line = _char_offset_to_line(text, char_offset)
    end_pos = char_offset + len(chunk_text)
    end_line = _char_offset_to_line(text, end_pos - 1)  # -1 for last char's line
    return (start_line, end_line)


def build_chunk_docs(
    markdown_content: str, file_name: str, collection_id: str
) -> List[Document]:
    """Split markdown into chunks and compute line-range metadata for each.

    Uses the markdown-aware splitter with ``add_start_index=True`` so that
    each :class:`Document` carries the character offset where it starts in
    the original text.  This avoids the bug where ``str.find()`` would
    always match the *first* occurrence of duplicate text.

    Returns:
        List of :class:`Document` objects with ``start_line``, ``end_line``,
        ``file_name`` and ``collection_id`` in their metadata.
    """
    split_docs = _splitter.create_documents([markdown_content])

    docs: List[Document] = []
    for split_doc in split_docs:
        start_index: int = split_doc.metadata.get("start_index", -1)
        if start_index < 0:
            raise ValueError(
                "Splitter did not provide start_index metadata. "
                "Ensure add_start_index=True."
            )

        start_line, end_line = _char_offset_to_line_range(
            markdown_content, start_index, split_doc.page_content
        )
        docs.append(
            Document(
                page_content=split_doc.page_content,
                metadata={
                    "start_line": start_line,
                    "end_line": end_line,
                    "file_name": file_name,
                    "collection_id": collection_id,
                },
            )
        )
    return docs


def get_file_hash_from_path(file_path: str) -> str:
    """Extract xxh128 hash from file path where hash is the filename."""
    return os.path.basename(file_path)


def get_collection_id(file_hash: str) -> str:
    """Generate pgvector collection ID from file hash."""
    return f"doc_chunks_{file_hash}"


class VectorStoreService:
    """Service for vector storage and retrieval operations."""

    def __init__(self, connection_string: str, openai_api_key: str):
        """Initialize vector store with database connection."""
        self.embeddings = init_embeddings(api_key=openai_api_key)

        # Always use async engine since all our methods are async
        # Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy async engine
        if connection_string.startswith("postgresql://"):
            async_url = connection_string.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        else:
            async_url = connection_string

        self.async_engine = create_async_engine(async_url)
        self._vectorstore_cache: dict[str, PGVector] = {}
        self._indexing_locks: dict[str, asyncio.Lock] = {}

        logger.info("VectorStore initialized with async engine")

    def _get_vectorstore(self, collection_id: str) -> PGVector:
        """
        Get or create a PGVector instance for a specific collection.
        Each document gets its own collection for efficient retrieval.
        """
        if collection_id not in self._vectorstore_cache:
            self._vectorstore_cache[collection_id] = PGVector(
                connection=self.async_engine,
                embeddings=self.embeddings,
                collection_name=collection_id,  # Each document has its own collection
                use_jsonb=True,
            )
            logger.debug(f"Created PGVector instance for collection: {collection_id}")

        return self._vectorstore_cache[collection_id]

    def _get_lock(self, collection_id: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock for a specific collection.

        Used to prevent concurrent indexing of the same collection when
        multiple coroutines call ensure_collection_indexed simultaneously.
        """

        return self._indexing_locks.setdefault(collection_id, asyncio.Lock())

    async def ensure_collection_indexed(
        self, collection_id: str, markdown_content: str, file_name: str
    ) -> None:
        """Ensure a collection is indexed, indexing it on-demand if needed.

        Uses a per-collection lock to prevent race conditions when multiple
        coroutines attempt to index the same collection concurrently.
        """
        async with self._get_lock(collection_id):
            if await self.is_collection_indexed(collection_id):
                logger.info(f"Collection {collection_id} already indexed, skipping")
                return

            logger.info(f"Collection {collection_id} not indexed, indexing on-demand")
            await self.index_document(
                markdown_content=markdown_content,
                file_name=file_name,
                collection_id=collection_id,
            )

    async def is_collection_indexed(self, collection_id: str) -> bool:
        """Check if collection is indexed."""

        vectorstore = self._get_vectorstore(collection_id)
        results = await vectorstore.asimilarity_search(query="", k=1)
        return len(results) > 0

    async def index_document(
        self, markdown_content: str, file_name: str, collection_id: str
    ) -> int:
        """
        Index document using semantic markdown-aware chunking.
        Returns number of chunks indexed.

        Uses RecursiveCharacterTextSplitter to split the markdown into
        semantically coherent chunks (respecting headings, paragraphs,
        and sentences), then embeds each chunk with start/end line metadata.
        """
        try:
            docs = build_chunk_docs(markdown_content, file_name, collection_id)

            vectorstore = self._get_vectorstore(collection_id)

            # Batch documents to avoid OpenAI's token limit per embedding request
            total_docs = len(docs)
            for batch_start in range(0, total_docs, EMBEDDING_BATCH_SIZE):
                batch_end = min(batch_start + EMBEDDING_BATCH_SIZE, total_docs)
                batch = docs[batch_start:batch_end]
                await vectorstore.aadd_documents(batch)
                logger.debug(
                    f"Indexed batch {batch_start}-{batch_end} of {total_docs} chunks"
                )

            logger.info(
                f"Indexed {total_docs} chunks for {file_name} "
                f"in collection {collection_id}"
            )
            return total_docs

        except Exception as e:
            raise Exception(
                f"Failed to index document '{file_name}' in collection {collection_id}"
            ) from e

    async def retrieve_relevant_passages(
        self, query: str, collection_id: str, top_k: int
    ) -> List[RetrievedPassage]:
        """
        Retrieve most relevant passages for query from a SPECIFIC collection.
        Each document has its own collection, so no filtering needed.
        Returns empty list on failure for graceful degradation.
        """
        try:
            vectorstore = self._get_vectorstore(collection_id)

            results = await vectorstore.asimilarity_search_with_score(query, k=top_k)

            logger.info(
                f"Retrieved {len(results)} passages from collection {collection_id} "
                f"for query: '{query}.'"
            )

            passages = []
            for doc, score in results:
                passages.append(
                    RetrievedPassage(
                        content=doc.page_content,
                        source_file=doc.metadata.get("file_name", "unknown"),
                        start_line=doc.metadata.get("start_line", 1),
                        end_line=doc.metadata.get("end_line", 1),
                        cosine_distance=float(score),
                    )
                )

            return passages

        except Exception as e:
            raise Exception(
                f"Retrieval failed for query '{query}' in collection {collection_id}"
            ) from e
