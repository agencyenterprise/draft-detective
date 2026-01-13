import logging
from typing import Any, Dict, Optional, Tuple

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummary, DocumentSummarizerAgent
from lib.run_utils import run_tasks
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentProcessingState

logger = logging.getLogger(__name__)

SUPPORTING_DOC_HEADER_SIZE = 4000


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
    "Summarize documents",
    "Summarize the main document and supporting documents",
)
async def summarize_documents(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)
    main_response = await document_summarizer_agent.ainvoke(
        {"document": state.file.markdown}
    )
    logger.info(f"Summarized main document: {main_response.summary.title}")

    supporting_summaries: Dict[int, DocumentSummary] = {}

    if state.supporting_files:
        logger.info(f"Summarizing {len(state.supporting_files)} supporting documents")

        tasks = [
            _summarize_supporting_doc(idx, f, document_summarizer_agent)
            for idx, f in enumerate(state.supporting_files)
        ]
        results, _ = await run_tasks(tasks, desc="Summarizing supporting documents")

        for result in results:
            if result is not None:
                idx, summary = result
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
