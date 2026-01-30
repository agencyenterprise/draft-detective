import asyncio
import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummarizerAgent
from lib.models.file import FileRole
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    FileSummary,
)

logger = logging.getLogger(__name__)

# Truncate supporting documents to this size for summarization
SUPPORTING_DOC_HEADER_SIZE = 4000


async def _summarize_document(
    document: FileDocument,
    agent: DocumentSummarizerAgent,
    existing_summaries: List[FileSummary],
    role: FileRole,
    runtime: Runtime[ContextSchema],
) -> FileSummary:
    # Return existing summary if already calculated
    existing = next(
        (s for s in existing_summaries if s.file_id == document.file_id), None
    )
    if existing:
        logger.info(f"Using existing summary for file {document.file_id}")
        return existing

    content = (
        document.markdown
        if role == FileRole.MAIN
        else document.markdown[:SUPPORTING_DOC_HEADER_SIZE]
    )
    response = await agent.ainvoke({"document": content})

    summary = FileSummary(file_id=document.file_id, **response.summary.model_dump())

    if role == FileRole.MAIN and runtime.context.project_id:
        from lib.services.projects import update_project_title

        # Update project title with main document summary title
        await update_project_title(
            project_id=runtime.context.project_id,
            title=summary.title,
        )

    return summary


@register_node(
    "Summarize documents",
    "Summarize the main document and supporting documents",
)
async def summarize_documents(
    state: DocumentSummarizationState, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    logger.info(
        f"Summarizing 1 (main) + {len(state.supporting_file_ids)} (supporting) documents"
    )

    existing_summaries = state.summaries or []

    # Load main document
    main_doc = await file_artifacts_service.get_file_document(state.main_file_id)

    # Load supporting documents
    supporting_docs = await asyncio.gather(
        *[
            file_artifacts_service.get_file_document(file_id)
            for file_id in state.supporting_file_ids
        ]
    )

    # Create tasks: main doc uses full content, supporting docs are truncated
    tasks = [
        _summarize_document(
            main_doc,
            document_summarizer_agent,
            existing_summaries,
            role=FileRole.MAIN,
            runtime=runtime,
        )
    ] + [
        _summarize_document(
            doc,
            document_summarizer_agent,
            existing_summaries,
            role=FileRole.SUPPORT,
            runtime=runtime,
        )
        for doc in supporting_docs
    ]

    results, exceptions = await run_tasks(tasks, desc="Summarizing documents")

    summaries: List[FileSummary] = [result for result in results if result is not None]
    errors = convert_exceptions_to_workflow_errors(
        "summarize_documents",
        exceptions,
        workflow_run_id=runtime.context.workflow_run_id,
    )

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
