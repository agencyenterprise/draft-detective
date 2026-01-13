import logging
from datetime import date

from langgraph.runtime import Runtime

from lib.agents.literature_review import LiteratureReviewAgent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.literature_review.state import LiteratureReviewState

logger = logging.getLogger(__name__)


@register_node(
    "Review literature",
    "Review the literature for the document",
)
async def literature_review(
    state: LiteratureReviewState, runtime: Runtime[ContextSchema]
):
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    file = await file_artifacts_service.get_file_document(state.file_id)
    references = await file_artifacts_service.get_references()

    markdown = file.markdown
    bibliography = references or []
    document_publication_date = (
        state.config.publication_date
        if state.config.publication_date
        else date.today().isoformat()
    )

    literature_review_agent = LiteratureReviewAgent(runtime.context)
    literature_review_response = await literature_review_agent.ainvoke(
        {
            "full_document": markdown,
            "bibliography": bibliography,
            "document_publication_date": document_publication_date,
        }
    )

    return {"literature_review": literature_review_response}
