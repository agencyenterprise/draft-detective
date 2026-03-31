import logging

from langgraph.runtime import Runtime

from lib.agents.reviewer_2 import Reviewer2Agent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reviewer_2.state import Reviewer2State

logger = logging.getLogger(__name__)


@register_node("Generate peer review")
async def generate_review(
    state: Reviewer2State, runtime: Runtime[ContextSchema]
) -> dict:
    """Produce a peer review with rebuttal using a deep agent."""
    file_artifacts_service = runtime.context.file_artifacts_service
    main_file = await file_artifacts_service.get_main_file()

    agent = Reviewer2Agent(runtime.context)
    result = await agent.ainvoke({"document_markdown": main_file.markdown})

    return {
        "peer_review_markdown": result.peer_review_markdown,
        "rebuttal_markdown": result.rebuttal_markdown,
    }
