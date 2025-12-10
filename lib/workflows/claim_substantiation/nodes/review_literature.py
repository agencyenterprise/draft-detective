import logging

from langgraph.runtime import Runtime

from lib.agents.literature_review import LiteratureReviewAgent
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Review literature",
    "Review the literature for the document",
)
async def literature_review(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:

    if not state.config.run_literature_review:
        logger.info(
            f"literature_review ({state.config.session_id}): skipping literature review (run_literature_review is False)"
        )
        return {}

    markdown = state.file.markdown

    literature_review_agent = LiteratureReviewAgent(runtime.context)
    literature_review_response = await literature_review_agent.ainvoke(
        {
            "full_document": markdown,
            "bibliography": state.references,
            "document_publication_date": state.config.document_publication_date.isoformat(),
        }
    )

    return {"literature_review": literature_review_response}
