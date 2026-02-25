import logging
from contextvars import ContextVar

from inspect_ai.hooks import Hooks, TaskStart, hooks
from inspect_ai.model import (
    Model,
    ModelName,
    get_model,
)
from inspect_ai.model._generate_config import active_generate_config
from inspect_ai.model._model import active_model
from langgraph.graph.state import RunnableConfig

from lib.config.langfuse import langfuse_handler
from lib.config.llm_models import LLMModel
from lib.models.agent import BaseAgent, LangChainAgent

logger = logging.getLogger(__name__)

_current_task_id: ContextVar[str | None] = ContextVar("_current_task_id", default=None)
_current_task_name: ContextVar[str | None] = ContextVar(
    "_current_task_name", default=None
)


@hooks(
    "langfuse_inspectai_metadata",
    "Captures InspectAI metadata information for Langfuse session tracking",
)
class _LangfuseInspectAIMetadataHook(Hooks):
    async def on_task_start(self, data: TaskStart) -> None:
        _current_task_id.set(data.spec.task_id)
        _current_task_name.set(data.spec.task)


def get_runnable_config() -> RunnableConfig:
    """Get a RunnableConfig for InspectAI evaluations."""

    task_id = _current_task_id.get()
    task_name = _current_task_name.get()

    run_name = "inspectai_eval"
    if task_name:
        run_name = f"inspectai_eval__{task_name}"

    metadata: dict[str, str] = {}
    if task_id:
        metadata["langfuse_session_id"] = task_id

    return RunnableConfig(
        run_name=run_name,
        callbacks=[langfuse_handler],
        metadata=metadata,
    )


def apply_inspectai_config_to_agent(agent: LangChainAgent) -> None:
    """
    Override a LangChainAgent's parameters with values from the current Inspect AI
    runtime (CLI flags like --model, --temperature, --reasoning-effort, etc.).

    Only non-None config values override the agent defaults. Resets the cached
    LLM so the next call picks up the new parameters.
    """

    config = active_generate_config()
    model = active_model()

    if model is not None and model.name != "none":
        inspectai_name = str(ModelName(model))
        if inspectai_name != agent.model.get_model_name_for_inspectai():
            agent.model = LLMModel.from_inspectai_name(inspectai_name)
            logger.info("Overriding model to %s", agent.model.model_name)

    if config.temperature is not None:
        agent.temperature = config.temperature
        logger.info("Overriding temperature to %s", config.temperature)

    if config.reasoning_effort is not None or config.reasoning_summary is not None:
        reasoning = dict(agent.reasoning) if agent.reasoning else {}
        if config.reasoning_effort is not None:
            reasoning["effort"] = config.reasoning_effort
            logger.info("Overriding reasoning effort to %s", config.reasoning_effort)
        if config.reasoning_summary is not None:
            reasoning["summary"] = config.reasoning_summary
            logger.info("Overriding reasoning summary to %s", config.reasoning_summary)
        agent.reasoning = reasoning  # type: ignore[assignment]

    agent._llm = None


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
