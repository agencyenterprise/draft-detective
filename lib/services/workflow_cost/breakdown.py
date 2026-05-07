from decimal import Decimal
from typing import Dict

from pydantic import BaseModel, Field


class UsageRecord(BaseModel):
    """Token usage extracted from a single AIMessage."""

    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


class ModelCostBreakdown(BaseModel):
    """Cost and token totals for a single model."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    input_cost_usd: Decimal = Field(default=Decimal("0"))
    output_cost_usd: Decimal = Field(default=Decimal("0"))
    cache_read_cost_usd: Decimal = Field(default=Decimal("0"))
    total_cost_usd: Decimal = Field(default=Decimal("0"))


class CostBreakdown(BaseModel):
    """Aggregated cost across all models used in a workflow run."""

    total_cost_usd: Decimal = Field(default=Decimal("0"))
    input_cost_usd: Decimal = Field(default=Decimal("0"))
    output_cost_usd: Decimal = Field(default=Decimal("0"))
    cache_read_cost_usd: Decimal = Field(default=Decimal("0"))
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    by_model: Dict[str, ModelCostBreakdown] = Field(default_factory=dict)
