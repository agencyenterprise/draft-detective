import logging
from typing import Dict

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummary, DocumentSummarizerAgent
from lib.run_utils import run_tasks
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)

SUPPORTING_DOC_HEADER_SIZE = 6000
MAX_CONCURRENT_SUMMARIES = 10


async def _summarize_supporting_doc(
    file_doc: FileDocument,
    agent: DocumentSummarizerAgent,
) -> DocumentSummary:
    """Summarize a single supporting document (header only for efficiency)."""
    header = file_doc.markdown[:SUPPORTING_DOC_HEADER_SIZE]
    response = await agent.ainvoke({"document": header})
    return response.summary


@register_node(
    "Summarize documents",
    "Summarize the main document and supporting documents for analysis",
)
async def summarize_documents(
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

        tasks = [
            _summarize_supporting_doc(f, document_summarizer_agent)
            for f in state.supporting_files
        ]

        results, _errors = await run_tasks(
            tasks,
            desc="Summarizing supporting documents",
            max_concurrent=MAX_CONCURRENT_SUMMARIES,
        )

        for idx, summary in enumerate(results):
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
