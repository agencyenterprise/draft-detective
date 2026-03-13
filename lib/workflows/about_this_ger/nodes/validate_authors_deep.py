"""Authors validation node using a deep agent."""

import logging

from langgraph.runtime import Runtime

from lib.agents.authors_validator import AuthorsValidatorAgent
from lib.services.app_configs import get_config
from lib.workflows.about_this_ger.config_keys import AUTHORS_PROMPT_KEY
from lib.workflows.about_this_ger.state import AboutThisGerState
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Validate authors",
    "Deep-agent check of the author biographies section",
)
async def validate_authors_deep(
    state: AboutThisGerState, runtime: Runtime[ContextSchema]
) -> dict:
    """Run the authors validator deep agent and store the result."""

    prompt_override = await get_config(AUTHORS_PROMPT_KEY)
    agent = AuthorsValidatorAgent(
        runtime.context, system_prompt_override=prompt_override
    )
    result = await agent.ainvoke({})

    logger.info(
        "[AboutThisGER] Authors validation: issues=%d",
        len(result.issues),
    )

    return {"authors_result": result}
