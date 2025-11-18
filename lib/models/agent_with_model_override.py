"""Agent wrapper that allows model override for testing."""

import inspect
import logging
from typing import Any, Dict, Optional

from langchain.chat_models import init_chat_model
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from pydantic import BaseModel

from lib.config.llm_models import LLMModel
from lib.models.agent import AgentProtocol

logger = logging.getLogger(__name__)


class TokenUsageCallback(BaseCallbackHandler):
    """Captures token usage from LLM responses."""

    def __init__(self):
        super().__init__()
        self.usage: Optional[Dict[str, int]] = None

    def on_llm_end(self, response, **kwargs):
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                self.usage = {
                    "input_tokens": token_usage.get("prompt_tokens", 0),
                    "output_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0),
                }


class AgentModelOverride:
    """Wrapper that overrides an agent's model for testing."""

    def __init__(
        self,
        base_agent: AgentProtocol,
        override_model: LLMModel,
        temperature: float | None = None,
        timeout: int | None = None,
    ):
        self.base_agent = base_agent
        self.override_model = override_model
        self.name = base_agent.name
        self.description = base_agent.description

        self._usage_callback = TokenUsageCallback()
        self._langfuse_handler = LangfuseCallbackHandler()
        self._llm = self._create_llm(temperature, timeout)

    def _create_llm(self, temperature: float | None, timeout: int | None):
        """Create LLM with override parameters."""
        original = self.base_agent.llm

        llm = init_chat_model(
            self.override_model.model_name,
            temperature=temperature or getattr(original, "temperature", 0.2),
            timeout=timeout or getattr(original, "timeout", 180),
        )

        # Preserve structured output if configured
        schema = self._extract_schema(original)
        if schema:
            try:
                llm = llm.with_structured_output(schema)
            except Exception as e:
                logger.warning(f"Failed to apply structured output: {e}")

        return llm

    def _extract_schema(self, original_llm):
        """Extract output schema from original LLM."""
        # Try get_output_schema method first
        if hasattr(original_llm, "get_output_schema"):
            schema = original_llm.get_output_schema()
            if schema:
                return schema

        # Fallback to bound.response_format
        if hasattr(original_llm, "bound"):
            response_format = getattr(original_llm.bound, "response_format", None)
            if response_format and hasattr(response_format, "schema"):
                return response_format.schema

        return None

    def _find_prompt_template(self):
        """Find prompt template in agent's module."""
        agent_module = inspect.getmodule(self.base_agent.__class__)
        if not agent_module:
            raise ValueError(f"Cannot find module for {self.base_agent.name}")

        for name, obj in inspect.getmembers(agent_module):
            if (
                hasattr(obj, "format_messages")
                and "prompt" in name.lower()
                and not inspect.isclass(obj)
            ):
                return obj

        raise ValueError(f"Cannot find prompt template for {self.base_agent.name}")

    async def ainvoke(
        self, prompt_kwargs: Dict[str, Any], config: RunnableConfig | None = None
    ) -> BaseModel:
        """Invoke agent with override model."""
        prompt_template = self._find_prompt_template()
        messages = prompt_template.format_messages(**prompt_kwargs)

        config = config or {}
        config["callbacks"] = [
            *config.get("callbacks", []),
            self._usage_callback,
            self._langfuse_handler,
        ]

        result = await self._llm.ainvoke(messages, config=config)
        self._update_langfuse_costs()
        return result

    def _update_langfuse_costs(self):
        """Update Langfuse with cost details."""
        try:
            if not self._usage_callback.usage or not hasattr(
                self._langfuse_handler, "client"
            ):
                return

            from lib.services.langfuse_metrics import get_model_pricing

            pricing = get_model_pricing(str(self.override_model))
            usage = self._usage_callback.usage

            input_cost = usage.get("input_tokens", 0) * (pricing.input_price or 0)
            output_cost = usage.get("output_tokens", 0) * (pricing.output_price or 0)

            self._langfuse_handler.client.update_current_generation(
                cost_details={
                    "input": input_cost,
                    "output": output_cost,
                    "total": input_cost + output_cost,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update Langfuse costs: {e}")

    def get_last_usage(self) -> Dict[str, int]:
        """Get token usage from last invocation."""
        if self._usage_callback.usage is None:
            raise RuntimeError(
                f"No token usage captured for {self.override_model}. "
                "LLM provider didn't return usage information."
            )
        return self._usage_callback.usage

    def get_last_trace_id(self) -> Optional[str]:
        """Get Langfuse trace ID from last invocation."""
        return self._langfuse_handler.last_trace_id

    @property
    def llm(self):
        """Expose LLM for compatibility."""
        return self._llm


def create_agent_with_model(
    agent: AgentProtocol, model: LLMModel, temperature: float | None = None
) -> AgentProtocol:
    """Create agent version with different model."""
    return AgentModelOverride(agent, model, temperature=temperature)
