import logging
from typing import Any, Dict, List, Optional

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummarizerAgent
from lib.run_utils import run_tasks
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentProcessingState, FileSummary
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)

SUPPORTING_DOC_HEADER_SIZE = 4000


async def _summarize_document(
    document: FileDocument,
    agent: DocumentSummarizerAgent,
    existing_summaries: List[FileSummary],
    size: int | None = None,
) -> FileSummary:
    # Return existing summary if already calculated
    existing = next(
        (s for s in existing_summaries if s.file_id == document.file_id), None
    )
    if existing:
        logger.info(f"Using existing summary for file {document.file_id}")
        return existing

    content = document.markdown[:size] if size else document.markdown
    response = await agent.ainvoke({"document": content})
    return FileSummary(file_id=document.file_id, **response.summary.model_dump())


@register_node(
    "Summarize documents",
    "Summarize the main document and supporting documents",
)
async def summarize_documents(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)

    logger.info(
        f"Summarizing 1 (main) + {len(state.supporting_files or [])} (supporting) documents"
    )

    existing_summaries = state.summaries or []

    tasks = [
        _summarize_document(
            state.file, document_summarizer_agent, existing_summaries, size=None
        )
    ] + [
        _summarize_document(
            f,
            document_summarizer_agent,
            existing_summaries,
            size=SUPPORTING_DOC_HEADER_SIZE,
        )
        for f in state.supporting_files or []
    ]

    results, exceptions = await run_tasks(tasks, desc="Summarizing documents")

    summaries: List[FileSummary] = [result for result in results if result is not None]
    errors = [
        WorkflowError(task_name="summarize_documents", error=str(exception))
        for exception in exceptions
        if exception is not None
    ]

    # Persist summary artifacts to database for caching
    _persist_summary_artifacts(summaries)

    return {"summaries": summaries, "errors": errors}


def _persist_summary_artifacts(summaries: List[FileSummary]) -> None:
    """
    Persist summary artifacts to the files table for all summarized documents.

    Args:
        summaries: List of FileSummary objects containing file_id and summary data
    """
    from lib.services.files import update_file_artifacts

    for summary in summaries:
        update_file_artifacts(
            file_id=summary.file_id,
            summary=summary.model_dump(exclude={"file_id"}),
        )
