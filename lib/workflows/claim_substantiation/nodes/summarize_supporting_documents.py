import logging

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import (
    DocumentSummarizerAgent,
    DocumentSummarizerResponse,
)
from lib.run_utils import run_tasks
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Summarize supporting documents",
    "Summarize the supporting documents",
)
async def summarize_supporting_documents(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:

    if not state.config.run_suggest_citations:
        logger.info(
            f"summarize_supporting_documents ({state.config.session_id}): skipping summarize_supporting_documents (run_suggest_citations is False)"
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

    return {"supporting_documents_summaries": summaries}
