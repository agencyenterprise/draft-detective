import logging

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
) -> LiteratureReviewState:
    markdown = state.file.markdown
    bibliography = state.references or []
    document_publication_date = state.config.document_publication_date.isoformat()

    literature_review_agent = LiteratureReviewAgent(runtime.context)
    literature_review_response = await literature_review_agent.ainvoke(
        {
            "full_document": markdown,
            "bibliography": bibliography,
            "document_publication_date": document_publication_date,
        }
    )

    return {"literature_review": literature_review_response}
