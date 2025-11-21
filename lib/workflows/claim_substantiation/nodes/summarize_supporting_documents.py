import logging

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import (
    DocumentSummarizerAgent,
    DocumentSummarizerResponse,
)
from lib.run_utils import run_tasks
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


@handle_workflow_node_errors()
async def summarize_supporting_documents(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"summarize_supporting_documents ({state.config.session_id}): starting")

    if not state.config.run_suggest_citations:
        logger.info(
            f"summarize_supporting_documents ({state.config.session_id}): skipping summarize_supporting_documents (run_suggest_citations is False)"
        )
        return {}

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "summarize_supporting_documents" not in agents_to_run:
        logger.info(
            f"summarize_supporting_documents ({state.config.session_id}): Skipping (not in agents_to_run)"
        )
        return {}

    supporting_files = state.supporting_files
    if not supporting_files:
        logger.info(
            f"summarize_supporting_documents ({state.config.session_id}): No supporting files to summarize"
        )
        return {}

    logger.info(
        f"summarize_supporting_documents ({state.config.session_id}): Summarizing {len(supporting_files)} files in parallel"
    )

    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)
    tasks = [
        document_summarizer_agent.ainvoke(
            {
                "document": file.markdown,
            }
        )
        for file in supporting_files
    ]
    results: tuple[list[DocumentSummarizerResponse], list[Exception]] = await run_tasks(
        tasks, desc="Summarizing supporting documents"
    )
    summary_responses, exceptions = results  # TODO: Handle exceptions as WorkflowErrors

    # Build dictionary from results
    summaries = {
        index: response.summary for index, response in enumerate(summary_responses)
    }

    logger.info(f"summarize_supporting_documents ({state.config.session_id}): done")
    return {"supporting_documents_summaries": summaries}
