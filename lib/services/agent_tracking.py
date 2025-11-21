"""Agent execution tracking for metrics collection.

Provides tracking wrappers and callbacks for capturing token usage,
execution time, and cost metrics during agent execution.
"""

import logging
import time
from typing import Any, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from pydantic import BaseModel, Field

from lib.config.llm_models import LLMModel
from lib.services.langfuse_metrics import calculate_metrics, ModelMetrics

logger = logging.getLogger(__name__)


class TokenUsageCallback(BaseCallbackHandler):
    """Captures token usage from LLM responses.

    This callback handler extracts token usage information from LLM outputs
    and stores it for metrics calculation.
    """

    def __init__(self):
        super().__init__()
        self.usage: Optional[dict[str, int]] = None

    def on_llm_end(self, response, **kwargs):
        """Capture token usage when LLM completes - handles OpenAI, Anthropic, and Google formats."""
        usage = self._extract_from_generations(
            response
        ) or self._extract_from_llm_output(response)
        if usage:
            self.usage = usage

    def _extract_from_generations(self, response) -> dict | None:
        """Extract usage from response.generations (Google Gemini format)."""
        if not hasattr(response, "generations") or not response.generations:
            return None

        for generation in response.generations:
            if not generation or len(generation) == 0:
                continue

            message = generation[0].message
            if not hasattr(message, "usage_metadata") or not message.usage_metadata:
                continue

            return self._normalize_usage(message.usage_metadata)

        return None

    def _extract_from_llm_output(self, response) -> dict | None:
        """Extract usage from response.llm_output (OpenAI/Anthropic format)."""
        if not hasattr(response, "llm_output") or not response.llm_output:
            return None

        llm_output = response.llm_output

        # Try OpenAI format
        if token_usage := llm_output.get("token_usage"):
            return self._normalize_usage(
                token_usage,
                input_key="prompt_tokens",
                output_key="completion_tokens",
            )

        # Try Anthropic format
        if usage := llm_output.get("usage"):
            if "input_tokens" in usage or "output_tokens" in usage:
                return self._normalize_usage(usage)

        return None

    def _get_token_value(
        self, source: dict | object, key: str, default: int = 0
    ) -> int:
        """Get token value from dict or object."""
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

    def _normalize_usage(
        self,
        source: dict | object,
        input_key: str = "input_tokens",
        output_key: str = "output_tokens",
    ) -> dict | None:
        """
        Normalize usage data from dict or object format to standard dict.

        Args:
            source: Dict or object containing usage data
            input_key: Key name to map to 'input_tokens'
            output_key: Key name to map to 'output_tokens'

        Examples:
            OpenAI: {"prompt_tokens": 10, "completion_tokens": 20}
            Anthropic: {"input_tokens": 10, "output_tokens": 20}
            Gemini: UsageMetadata(input_tokens=10, output_tokens=20)
        """
        input_tokens = self._get_token_value(source, input_key)
        output_tokens = self._get_token_value(source, output_key)
        total_tokens = self._get_token_value(
            source, "total_tokens", input_tokens + output_tokens
        )

        # Validate we got real data
        if input_tokens == 0 and output_tokens == 0:
            return None

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def get_usage(self) -> dict[str, int]:
        """Get captured token usage.

        Returns:
            Dictionary with input_tokens, output_tokens, and total_tokens.
            Returns zeros if no usage was captured.
        """
        if self.usage is None:
            logger.warning(
                "No token usage captured - LLM provider may not return usage info"
            )
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        return self.usage


class AgentExecutionTracker:
    """Tracks execution metrics for a single agent run.

    Combines token tracking, timing, and Langfuse integration.
    """

    def __init__(self, model: LLMModel):
        """Initialize tracker for a specific model.

        Args:
            model: The LLM model being used for this execution
        """
        self.model = model
        self.token_callback = TokenUsageCallback()
        self.langfuse_handler = LangfuseCallbackHandler()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def get_callbacks(self) -> list[BaseCallbackHandler]:
        """Get callback handlers to attach to agent execution.

        Returns:
            List of callback handlers for tracking
        """
        return [self.token_callback, self.langfuse_handler]

    def start_timing(self):
        """Start execution timer."""
        self.start_time = time.time()

    def stop_timing(self):
        """Stop execution timer."""
        self.end_time = time.time()

    def get_execution_time(self) -> float:
        """Get execution duration in seconds.

        Returns:
            Execution time in seconds, or 0 if timing wasn't used
        """
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    def get_metrics(self) -> ModelMetrics:
        """Calculate and return execution metrics.

        Returns:
            ModelMetrics with cost, tokens, and timing information
        """
        usage = self.token_callback.get_usage()
        execution_time = self.get_execution_time()

        metrics = calculate_metrics(
            model_name=str(self.model),
            execution_time=execution_time,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

        logger.debug(
            f"Execution metrics for {self.model}: "
            f"cost=${metrics.cost_usd:.4f}, duration={metrics.duration_seconds:.2f}s, "
            f"tokens={metrics.total_tokens}"
        )

        return metrics

    def update_langfuse_costs(self):
        """Update Langfuse trace with cost details."""
        try:
            if not self.token_callback.usage or not hasattr(
                self.langfuse_handler, "client"
            ):
                return

            from lib.services.langfuse_metrics import get_model_pricing

            pricing = get_model_pricing(str(self.model))
            usage = self.token_callback.usage

            input_cost = usage.get("input_tokens", 0) * (pricing.input_price or 0)
            output_cost = usage.get("output_tokens", 0) * (pricing.output_price or 0)

            self.langfuse_handler.client.update_current_generation(
                cost_details={
                    "input": input_cost,
                    "output": output_cost,
                    "total": input_cost + output_cost,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update Langfuse costs: {e}")
