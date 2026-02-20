from inspect_ai.model import GenerateConfig, Model, ResponseSchema, get_model
from inspect_ai.util import json_schema
from pydantic import BaseModel

from lib.models.agent import BaseAgent


def generate_config_for_agent(
    agent_class: type[BaseAgent], output_schema: type[BaseModel]
) -> GenerateConfig:
    """
    Create a InspectAI GenerateConfig for an agent. Uses default parameters defined in the agent class. Notice that these can be overridden by the caller, if, for example, inspectAI is invoked with parameters (`--reasoning-effort`, `--reasoning-summary`, `--temperature` etc).

    Args:
        agent_class: The agent class to create a GenerateConfig for
        output_schema: The structured output schema for the agent

    Returns:
        A InspectAI GenerateConfig for the agent
    """

    reasoning_effort = (
        agent_class.reasoning["effort"] if agent_class.reasoning else None
    )
    reasoning_summary = (
        agent_class.reasoning["summary"] if agent_class.reasoning else None
    )
    temperature = agent_class.temperature
    name = agent_class.name.lower().replace(" ", "_")

    return GenerateConfig(
        reasoning_effort=reasoning_effort,
        reasoning_summary=reasoning_summary,
        temperature=temperature,
        response_schema=ResponseSchema(
            name=name,
            json_schema=json_schema(output_schema),
            strict=False,
        ),
    )


def get_model_or_agent_default(agent_class: type[BaseAgent]) -> Model:
    """
    Get the InspectAI Model current in use (defined via task arguments) or use the default model for the agent.

    Args:
        agent_class: The agent class to get the model for, as default, in case no model is defined via task arguments

    Returns:
        The InspectAI Model
    """

    task_model = get_model()

    if not task_model or task_model.name == "none":
        return get_model(agent_class.model.get_model_name_for_inspectai())

    return task_model
