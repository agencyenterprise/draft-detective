import logging

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummarizerAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


@handle_workflow_node_errors()
async def prepare_documents(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"prepare_documents ({state.config.session_id}): starting")

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "prepare_documents" not in agents_to_run:
        logger.info(
            f"prepare_documents ({state.config.session_id}): Skipping prepare_documents (not in agents_to_run)"
        )
        return {}

    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)

    response = await document_summarizer_agent.ainvoke(
        {
            "document": state.file.markdown,
        }
    )

    logger.info(f"prepare_documents ({state.config.session_id}): done")

    return {"main_document_summary": response.summary}
