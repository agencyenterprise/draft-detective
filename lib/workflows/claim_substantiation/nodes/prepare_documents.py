import logging

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummarizerAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Prepare documents",
    "Prepare documents for analysis, including summarizing the main document and supporting documents",
)
async def prepare_documents(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)

    # only summarize document if it exceeds 7500 characters
    if len(state.file.markdown) > 7500:
        response = await document_summarizer_agent.ainvoke(
            {
                "document": state.file.markdown,
            }
        )
    else:
        response = {"summary": state.file.markdown}

    return {"main_document_summary": response.summary}
