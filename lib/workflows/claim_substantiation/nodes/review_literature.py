import logging

from langgraph.runtime import Runtime

from lib.agents.literature_review import LiteratureReviewAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


@handle_workflow_node_errors()
async def literature_review(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"literature_review ({state.config.session_id}): starting")

    if not state.config.run_literature_review:
        logger.info(
            f"literature_review ({state.config.session_id}): skipping literature review (run_literature_review is False)"
        )
        return {}

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "literature_review" not in agents_to_run:
        logger.info(
            f"literature_review ({state.config.session_id}): Skipping literature review (not in agents_to_run)"
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

    logger.info(f"literature_review ({state.config.session_id}): done")
    return {"literature_review": literature_review_response}
