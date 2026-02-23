import logging
from typing import Optional

from lib.config.llm_models import LLMModel
from lib.models.agent import BaseAgent, LangChainAgent

logger = logging.getLogger(__name__)


def create_agent_with_model(
    base_agent: BaseAgent,
    model: Optional[LLMModel] = None,
    temperature: Optional[float] = None,
    timeout: Optional[int] = None,
) -> BaseAgent:
    """Create a new agent instance with overridden model configuration.

    Args:
        base_agent: The base agent to create a variant from
        model: The model to use for this agent instance
        temperature: Optional temperature override (uses base agent's if not provided)
        timeout: Optional timeout override (uses base agent's if not provided)

    Returns:
        New agent instance with the specified model configuration

    Example:
        ```python
        from lib.agents.claim_extractor import claim_extractor_agent
        from lib.config.llm_models import gpt_5_model

        # Create variant with different model
        test_agent = create_agent_with_model(claim_extractor_agent, gpt_5_model)
        result = await test_agent.ainvoke(prompt_kwargs)
        ```
    """
    agent_class = base_agent.__class__

    # Pass context if the agent requires it (LangChainAgent or DirectOpenAIAgent)
    if hasattr(base_agent, "context"):
        new_agent = agent_class(context=base_agent.context)
    else:
        new_agent = agent_class()

    new_agent.model = model
    new_agent.temperature = (
        temperature if temperature is not None else base_agent.temperature
    )
    new_agent.timeout = timeout if timeout is not None else base_agent.timeout

    # Reset cached LLM to force recreation with new configuration
    if isinstance(new_agent, LangChainAgent):
        new_agent._llm = None

    logger.debug(
        f"Created agent variant: {new_agent.name} with model={model.model_name if model else None}, "
        f"temperature={new_agent.temperature}, timeout={new_agent.timeout}"
    )

    return new_agent


def create_agents_for_models(
    base_agent: BaseAgent,
    models: list[LLMModel],
    temperature: Optional[float] = None,
    timeout: Optional[int] = None,
) -> list[BaseAgent]:
    """Create multiple agent instances, one per model.

    Convenience function for creating multiple agent variants at once.

    Args:
        base_agent: The base agent to create variants from
        models: List of models to create agents for
        temperature: Optional temperature override for all agents
        timeout: Optional timeout override for all agents

    Returns:
        List of agent instances, one per model
    """
    return [
        create_agent_with_model(base_agent, model, temperature, timeout)
        for model in models
    ]
