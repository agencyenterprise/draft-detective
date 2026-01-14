import logging
import os
from typing import List, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger(__name__)

# RAG retrieval settings
RAG_TOP_K = 20  # Number of passages to retrieve per query

# RAG chunking settings (all in characters)
RAG_CHUNK_SIZE = 2000  # Characters per chunk when indexing documents
RAG_CHUNK_OVERLAP = 400  # Character overlap between adjacent chunks

# Batching settings for OpenAI embedding API
# With ~2000 char chunks averaging ~500-1000 tokens each, 100 chunks is ~50-100k tokens (safe margin for the 300k limit)
EMBEDDING_BATCH_SIZE = 100

EMBEDDING_MODEL = "text-embedding-3-large"


class RetrievedPassage(BaseModel):
    """Represents a passage retrieved from vector store."""

    content: str = Field(description="The text content of the retrieved passage")
    source_file: str = Field(description="Name of the source file")
    chunk_index: int = Field(description="Index of the chunk within the source")
    cosine_distance: float = Field(
        description="Cosine distance (0-1, lower = more similar)"
    )
    page_number: Optional[str] = Field(
        default=None, description="Page number if available"
    )


def get_file_hash_from_path(file_path: str) -> str:
    """Extract xxh128 hash from file path where hash is the filename."""
    return os.path.basename(file_path)


def get_collection_id(file_hash: str) -> str:
    """Generate pgvector collection ID from file hash."""
    return f"doc_passages_{file_hash}"


class VectorStoreService:
    """Service for vector storage and retrieval operations."""

    def __init__(self, connection_string: str, openai_api_key: str):
        """Initialize vector store with database connection."""
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL, api_key=openai_api_key
        )
        self.chunker = RecursiveCharacterTextSplitter(
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

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

    async def is_collection_indexed(self, collection_id: str) -> bool:
        """Check if collection is indexed."""

        vectorstore = self._get_vectorstore(collection_id)
        results = await vectorstore.asimilarity_search(query="", k=1)
        return len(results) > 0

    async def index_document(
        self, markdown_content: str, file_name: str, collection_id: str
    ) -> int:
        """
        Chunk, embed, and index document.
        Returns number of chunks indexed.

        Documents are batched to stay under OpenAI's token limit per request.
        """
        try:
            # Create document chunks and set metadata
            docs = self.chunker.create_documents([markdown_content])
            for i, doc in enumerate(docs):
                doc.metadata["chunk_index"] = i
                doc.metadata["file_name"] = file_name
                doc.metadata["collection_id"] = collection_id

            vectorstore = self._get_vectorstore(collection_id)

            # Batch documents to avoid OpenAI's token limit per embedding request
            total_chunks = len(docs)
            for batch_start in range(0, total_chunks, EMBEDDING_BATCH_SIZE):
                batch_end = min(batch_start + EMBEDDING_BATCH_SIZE, total_chunks)
                batch = docs[batch_start:batch_end]
                await vectorstore.aadd_documents(batch)
                logger.debug(
                    f"Indexed batch {batch_start}-{batch_end} of {total_chunks} chunks"
                )

            logger.info(
                f"Indexed {total_chunks} chunks for {file_name} in collection {collection_id}"
            )
            return total_chunks

        except Exception as e:
            raise Exception(
                f"Failed to index document '{file_name}' in collection {collection_id}"
            ) from e

    async def retrieve_relevant_passages(
        self, query: str, collection_id: str, top_k: int = RAG_TOP_K
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
                        chunk_index=doc.metadata.get("chunk_index", 0),
                        cosine_distance=float(score),
                        page_number=doc.metadata.get("page_number"),
                    )
                )

            return passages

        except Exception as e:
            raise Exception(
                f"Retrieval failed for query '{query}' in collection {collection_id}"
            ) from e
