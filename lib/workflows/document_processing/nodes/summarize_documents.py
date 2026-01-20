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

    # Persist summary artifacts to database for caching
    _persist_summary_artifacts(
        main_file_id=state.file.file_id,
        main_summary=main_response.summary,
        supporting_files=state.supporting_files,
        supporting_summaries=supporting_summaries,
    )

    return {
        "main_document_summary": main_response.summary,
        "supporting_documents_summaries": supporting_summaries,
    }


def _persist_summary_artifacts(
    main_file_id: str,
    main_summary: DocumentSummary,
    supporting_files: Optional[list[FileDocument]],
    supporting_summaries: Dict[int, DocumentSummary],
) -> None:
    """
    Persist summary artifacts to the files table for all summarized documents.

    Args:
        main_file_id: The file ID of the main document
        main_summary: The summary of the main document
        supporting_files: List of supporting documents
        supporting_summaries: Dictionary mapping indices to summaries
    """
    from lib.services.files import update_file_artifacts

    # Persist main file summary
    update_file_artifacts(
        file_id=main_file_id,
        summary=main_summary.model_dump(),
    )

    # Persist supporting files summaries
    if supporting_files:
        for idx, summary in supporting_summaries.items():
            supporting_file = supporting_files[idx]
            update_file_artifacts(
                file_id=supporting_file.file_id,
                summary=summary.model_dump(),
            )
