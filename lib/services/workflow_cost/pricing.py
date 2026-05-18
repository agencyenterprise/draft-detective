import asyncio
import logging
import re
from decimal import Decimal
from typing import Any, Iterable, Optional

from lib.services.workflow_cost.breakdown import (
    CostBreakdown,
    ModelCostBreakdown,
    UsageRecord,
)

logger = logging.getLogger(__name__)

# Cached compiled (pattern, model) tuples loaded from Langfuse. None means not loaded.
# Tests can set this directly to bypass the network fetch.
_MODELS_CACHE: Optional[list[tuple[re.Pattern[str], Any]]] = None
_MODELS_LOCK = asyncio.Lock()


async def _ensure_models_loaded() -> list[tuple[re.Pattern[str], Any]]:
    """Lazy-load and cache the Langfuse model price catalog for the process lifetime."""
    global _MODELS_CACHE
    cached = _MODELS_CACHE
    if cached is not None:
        return cached
    async with _MODELS_LOCK:
        cached = _MODELS_CACHE
        if cached is not None:
            return cached

        # Imported lazily to avoid creating the Langfuse client at import time
        # (langfuse is None when env vars are not configured).
        from lib.config.langfuse import langfuse

        if langfuse is None:
            logger.info("Langfuse not configured; cost calculation disabled")
            _MODELS_CACHE = []
            return _MODELS_CACHE

        models: list = []
        page = 1
        while True:
            res = await langfuse.async_api.models.list(page=page, limit=100)
            models.extend(res.data)
            if len(models) >= res.meta.total_items:
                break
            page += 1

        compiled: list[tuple[re.Pattern[str], Any]] = []
        for m in models:
            try:
                compiled.append((re.compile(m.match_pattern), m))
            except re.error as e:
                logger.warning(
                    "skipping invalid Langfuse model pattern %r: %s",
                    m.match_pattern,
                    e,
                )
        logger.info("loaded %d model price entries from Langfuse", len(compiled))
        _MODELS_CACHE = compiled
        return _MODELS_CACHE


def _match_model(
    name: str, models: list[tuple[re.Pattern[str], Any]]
) -> Optional[Any]:
    for pattern, model in models:
        if pattern.fullmatch(name):
            return model
    return None


def _rate(prices: dict, *keys: str) -> Decimal:
    for k in keys:
        price = prices.get(k)
        if price is not None:
            return Decimal(str(price.price))
    return Decimal("0")


def _cost_for_record(
    record: UsageRecord, models: list[tuple[re.Pattern[str], Any]]
) -> ModelCostBreakdown | None:
    model = _match_model(record.model_name, models)
    if model is None:
        logger.warning(
            "Langfuse has no pricing for model %r; skipping cost calc",
            record.model_name,
        )
        return None

    prices = model.prices
    input_rate = _rate(prices, "input")
    output_rate = _rate(prices, "output")
    # Fall back to input rate when no cache_read price is published.
    cache_read_rate = _rate(prices, "input_cache_read", "input_cached_tokens", "input")

    input_cost = input_rate * record.input_tokens
    output_cost = output_rate * record.output_tokens
    cache_read_cost = cache_read_rate * record.cache_read_tokens

    return ModelCostBreakdown(
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cache_read_tokens=record.cache_read_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        cache_read_cost_usd=cache_read_cost,
        total_cost_usd=input_cost + output_cost + cache_read_cost,
    )


def _accumulate(target: ModelCostBreakdown, addition: ModelCostBreakdown) -> None:
    target.input_tokens += addition.input_tokens
    target.output_tokens += addition.output_tokens
    target.cache_read_tokens += addition.cache_read_tokens
    target.input_cost_usd += addition.input_cost_usd
    target.output_cost_usd += addition.output_cost_usd
    target.cache_read_cost_usd += addition.cache_read_cost_usd
    target.total_cost_usd += addition.total_cost_usd


async def compute_cost(records: Iterable[UsageRecord]) -> CostBreakdown | None:
    """Aggregate UsageRecords into a CostBreakdown using Langfuse pricing.

    Returns None when no records can be priced (no input or all models unknown).
    """
    records_list = list(records)
    if not records_list:
        return None

    models = await _ensure_models_loaded()
    if not models:
        return None

    breakdown = CostBreakdown()
    has_any = False
    for record in records_list:
        per_model = _cost_for_record(record, models)
        if per_model is None:
            continue
        has_any = True

        bucket = breakdown.by_model.setdefault(record.model_name, ModelCostBreakdown())
        _accumulate(bucket, per_model)
        bucket.request_count += 1

        breakdown.total_input_tokens += per_model.input_tokens
        breakdown.total_output_tokens += per_model.output_tokens
        breakdown.total_cache_read_tokens += per_model.cache_read_tokens
        breakdown.input_cost_usd += per_model.input_cost_usd
        breakdown.output_cost_usd += per_model.output_cost_usd
        breakdown.cache_read_cost_usd += per_model.cache_read_cost_usd
        breakdown.total_cost_usd += per_model.total_cost_usd
        breakdown.request_count += 1

    return breakdown if has_any else None
