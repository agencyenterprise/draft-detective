import logging

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummarizerAgent
from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Prepare documents",
    "Prepare documents for analysis, including summarizing the main document and supporting documents",
)
async def prepare_documents(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
) -> DocumentProcessingState:
    document_summarizer_agent = DocumentSummarizerAgent(runtime.context)
    response = await document_summarizer_agent.ainvoke(
        {
            "document": state.file.markdown,
        }
    )
    return {"main_document_summary": response.summary}

