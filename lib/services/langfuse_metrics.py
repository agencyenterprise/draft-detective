"""Utility functions for tracking cost and timing metrics from Langfuse.

This module provides utilities to calculate costs based on Langfuse model pricing.
Costs are retrieved from Langfuse's model definitions.

See: https://langfuse.com/docs/observability/features/token-and-cost-tracking
"""

import re
import logging
from functools import lru_cache
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ModelPricing(BaseModel):
    """Model pricing information from Langfuse."""

    input_price: Optional[float] = None
    output_price: Optional[float] = None


class ModelMetrics(BaseModel):
    """Calculated metrics for a model run."""

    cost_usd: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_seconds: float


def _extract_pricing_from_model(model) -> ModelPricing:
    """Extract pricing from a Langfuse model object.

    Args:
        model: Langfuse model object

    Returns:
        ModelPricing with input and output prices
    """
    # Extract pricing - models have direct attributes (We need for GPT-4.1 and below)
    input_price = getattr(model, "input_price", None)
    output_price = getattr(model, "output_price", None)
    total_price = getattr(model, "total_price", None)

    # Fallback to prices dict if direct attributes are None (We need for GPT-5 and above)
    if input_price is None or output_price is None:
        prices_dict = getattr(model, "prices", None)
        if prices_dict and isinstance(prices_dict, dict):
            if input_price is None and "input" in prices_dict:
                input_price = getattr(prices_dict["input"], "price", None)
            if output_price is None and "output" in prices_dict:
                output_price = getattr(prices_dict["output"], "price", None)
            if total_price is None and "total" in prices_dict:
                total_price = getattr(prices_dict["total"], "price", None)

    # If only total price is available, use it for input
    if total_price is not None and (input_price is None or output_price is None):
        input_price = total_price
        output_price = 0.0

    return ModelPricing(
        input_price=input_price,
        output_price=output_price,
    )


@lru_cache(maxsize=128)
def get_model_pricing(model_name: str) -> ModelPricing:
    """Get model pricing from Langfuse (cached).

    Args:
        model_name: Name of the model (e.g., "openai:gpt-4o", "claude-3-5-sonnet-20241022")

    Returns:
        ModelPricing with input_price and output_price (None if not available)
    """
    from lib.config.langfuse import langfuse

    if ":" in model_name:
        _, model_name_only = model_name.split(":", 1)
    else:
        model_name_only = model_name

    try:
        # Currently, we need to paginate through list() to find the matching model, since we do not have a search/match/find method
        page = 1
        while True:
            models = langfuse.api.models.list(page=page, limit=100)

            for model in models.data:
                match_pattern = getattr(model, "match_pattern", None)
                if not match_pattern:
                    continue

                try:
                    if re.match(match_pattern, model_name_only, re.IGNORECASE):
                        return _extract_pricing_from_model(model)
                except re.error:
                    continue

            if not hasattr(models, "meta") or not hasattr(models.meta, "total_pages"):
                break
            if page >= models.meta.total_pages:
                break

            page += 1

        logger.warning(
            f"No pricing found for model '{model_name}' (tried '{model_name_only}') in Langfuse"
        )
        return ModelPricing()

    except Exception as e:
        logger.error(f"Failed to fetch model pricing for {model_name}: {e}")
        return ModelPricing()


def calculate_metrics(
    model_name: str,
    execution_time: float,
    input_tokens: int,
    output_tokens: int,
) -> ModelMetrics:
    """Calculate cost and metrics for a model run.

    Args:
        model_name: Name of the model (e.g., "gpt-4o")
        execution_time: Time taken in seconds
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used

    Returns:
        ModelMetrics with cost and token information
    """
    pricing = get_model_pricing(model_name)

    cost_usd = 0.0
    if pricing.input_price is not None and pricing.output_price is not None:
        cost_usd = (input_tokens * pricing.input_price) + (
            output_tokens * pricing.output_price
        )

    return ModelMetrics(
        cost_usd=cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        duration_seconds=execution_time,
    )
