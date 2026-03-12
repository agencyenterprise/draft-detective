"""Preface validation node using a deep agent."""

import logging

from langgraph.runtime import Runtime

from lib.agents.preface_validator import PrefaceValidatorAgent
from lib.workflows.about_this_ger.state import AboutThisGerState
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Validate preface",
    "Deep-agent check of the preface / introduction section",
)
async def validate_preface_deep(
    state: AboutThisGerState, runtime: Runtime[ContextSchema]
) -> dict:
    """Run the preface validator deep agent and store the result."""

    agent = PrefaceValidatorAgent(runtime.context)
    result = await agent.ainvoke({})

    logger.info(
        "[AboutThisGER] Preface validation: issues=%d",
        len(result.issues),
    )

    return {"preface_result": result}
