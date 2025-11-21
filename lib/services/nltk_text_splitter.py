import asyncio
import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_text_splitters.base import TextSplitter

from lib.agents.document_chunker import DocumentChunkerAgent
from lib.agents.document_chunker_nltk import get_chunker_result_as_langchain_documents
from lib.agents.models import ValidatedDocument
from lib.workflows.claim_substantiation.context import ContextSchema

logger = logging.getLogger(__name__)


class NLTKTextSplitter(TextSplitter):
    """
    Text splitter using NLTK-based chunker with LLM fallback.

    This is faster and cheaper than LLMTextSplitter because it uses:
    1. NLTK for most paragraphs
    2. Fragment detection to identify citations/complex text
    3. LLM fallback only when needed
    """

    def __init__(self, context: ContextSchema):
        self.document_chunker_agent = DocumentChunkerAgent(context=context)

    async def split_text(self, text: str) -> List[ValidatedDocument]:
        result = await self.document_chunker_agent.ainvoke(
            prompt_kwargs={
                "full_document": text,
            }
        )
        return get_chunker_result_as_langchain_documents(result)

    async def create_documents(
        self, texts: List[str], metadatas: Optional[List[dict]] = None
    ) -> List[Document]:
        split_tasks = [self.split_text(text) for text in texts]
        async_results = await asyncio.gather(*split_tasks, return_exceptions=True)
        docs = []
        for result in async_results:
            if isinstance(result, Exception):
                raise result
            docs.extend(result)
        return docs
