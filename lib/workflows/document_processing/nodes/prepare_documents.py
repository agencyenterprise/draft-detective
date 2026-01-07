import asyncio
import logging
from typing import Dict, Optional, Tuple

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummary, DocumentSummarizerAgent
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)

SUPPORTING_DOC_HEADER_SIZE = 4000
MAX_CONCURRENT_SUMMARIES = 10


async def _summarize_supporting_doc(
    idx: int,
    file_doc: FileDocument,
    agent: DocumentSummarizerAgent,
) -> Tuple[int, Optional[DocumentSummary]]:
    """Summarize a single supporting document (header only for efficiency)."""
    try:
        header = file_doc.markdown[:SUPPORTING_DOC_HEADER_SIZE]
        response = await agent.ainvoke({"document": header})
        return (idx, response.summary)
    except Exception as e:
        logger.warning(f"Failed to summarize {file_doc.file_name}: {e}")
        return (idx, None)


@register_node(
    "Prepare documents",
    "Prepare documents for analysis, including summarizing the main document and supporting documents",
)
async def prepare_documents(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
) -> DocumentProcessingState:
    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)
    main_response = await document_summarizer_agent.ainvoke(
        {"document": state.file.markdown}
    )
    logger.info(f"Summarized main document: {main_response.summary.title}")

    supporting_summaries: Dict[int, DocumentSummary] = {}

    if state.supporting_files:
        logger.info(f"Summarizing {len(state.supporting_files)} supporting documents")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SUMMARIES)

        async def summarize_with_limit(idx: int, file_doc: FileDocument):
            async with semaphore:
                return await _summarize_supporting_doc(
                    idx, file_doc, document_summarizer_agent
                )

        results = await asyncio.gather(
            *[
                summarize_with_limit(idx, f)
                for idx, f in enumerate(state.supporting_files)
            ]
        )

        for idx, summary in results:
            if summary:
                supporting_summaries[idx] = summary
                logger.debug(f"Summarized supporting doc {idx}: {summary.title}")

        logger.info(
            f"Successfully summarized {len(supporting_summaries)}/{len(state.supporting_files)} supporting documents"
        )

    return {
        "main_document_summary": main_response.summary,
        "supporting_documents_summaries": supporting_summaries,
    }
