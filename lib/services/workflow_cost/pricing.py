"""Cost calculation from token usage, priced from the `genai-prices` dataset.

Prices ship inside the `genai-prices` package rather than being fetched from a
price API, so cost calculation needs no network, no cache and no staleness
handling: a new model becomes priceable by bumping the dependency. This replaced
a Langfuse-catalog lookup that priced none of the models this codebase actually
runs on -- every assessment on the RAND deployment reported no cost at all.
"""

import logging
import re
from decimal import Decimal
from functools import lru_cache
from typing import Iterable, Iterator, Optional

from genai_prices import Usage, calc_price
from genai_prices.types import PriceCalculation

from lib.services.workflow_cost.breakdown import (
    CostBreakdown,
    ModelCostBreakdown,
    UsageRecord,
)

logger = logging.getLogger(__name__)


# Providers report the deployed snapshot in response metadata, not the alias that
# was requested: asking for `gpt-5.6-terra` comes back as `gpt-5.6-terra-2026-07-09`
# from OpenAI, and as `gpt-5.6-terra-2026-07-09-global-aaif` through the Azure
# gateway the RAND deployment uses. `genai-prices` matches the bare dated form
# itself, so this only has to strip a trailing deployment suffix. Anchoring on the
# date keeps a genuinely different variant (`gpt-5.6-terra-mini`) from being priced
# as the base model.
_SNAPSHOT_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}(-.*)?$")

# `genai-prices` infers the provider from the model name, and declines names it
# cannot place on its own -- OpenAI's embedding and `-latest` models among them.
# Naming a provider resolves those. Only reached once the unqualified lookup has
# already failed, so there is no ambiguity for the order to resolve wrongly.
_FALLBACK_PROVIDERS = ("openai", "anthropic", "google")

# Nominal usage for probing whether a name resolves to a model at all. Any
# valid usage would do -- the answer does not depend on the counts.
_PROBE_USAGE = Usage(input_tokens=1)


def _model_refs(model_name: str) -> Iterator[tuple[str, Optional[str]]]:
    """`(model_ref, provider_id)` pairs to try for `model_name`, best first."""
    aliases = [model_name]
    alias = _SNAPSHOT_SUFFIX.sub("", model_name, count=1)
    if alias != model_name:
        aliases.append(alias)

    for ref in aliases:
        yield ref, None
    for ref in aliases:
        for provider in _FALLBACK_PROVIDERS:
            yield ref, provider


@lru_cache(maxsize=512)
def _resolve(model_name: str) -> Optional[tuple[str, Optional[str]]]:
    """The `(model_ref, provider_id)` pair `genai-prices` accepts for this name.

    Matching a name to a model does not depend on the token counts, so it is
    probed once per name and reused. Without the cache every record re-pays for
    the failing lookup of the reported snapshot name before the alias succeeds,
    which on the Azure-gateway names is half the cost of pricing a record.
    """
    for ref, provider in _model_refs(model_name):
        try:
            calc_price(_PROBE_USAGE, model_ref=ref, provider_id=provider)
        except LookupError:
            continue
        return ref, provider
    return None


def _price(model_name: str, usage: Usage) -> Optional[PriceCalculation]:
    """Price `usage` for `model_name`. None when no known model matches it."""
    resolved = _resolve(model_name)
    if resolved is None:
        return None
    ref, provider = resolved
    return calc_price(usage, model_ref=ref, provider_id=provider)


def _cache_read_cost(
    model_name: str, input_total: int, cache_read_tokens: int, input_price: Decimal
) -> Decimal:
    """The share of `input_price` owed to cache reads.

    `PriceCalculation.input_price` bundles cached and uncached input, but the UI
    itemises them. Pricing the same request size as if every input token were a
    cache read gives the cached per-token rate. Asking at the same size is the
    point: rates step up above a context threshold and apply to the whole
    request, so a smaller probe would land in a cheaper tier and understate the
    cached share.
    """
    if not cache_read_tokens or not input_total:
        return Decimal(0)
    if cache_read_tokens == input_total:
        # Nothing uncached to separate out, so the input price is all cache read.
        return input_price

    all_cached = _price(
        model_name,
        Usage(input_tokens=input_total, cache_read_tokens=input_total),
    )
    if all_cached is None:
        return Decimal(0)
    return all_cached.input_price / input_total * cache_read_tokens


def _cost_for_record(record: UsageRecord) -> ModelCostBreakdown | None:
    # `genai-prices` counts cache reads as part of `input_tokens`, the way the
    # providers report them. `UsageRecord` holds the two disjoint (see
    # `extractor._extract_record`), so they are added back together here.
    input_total = record.input_tokens + record.cache_read_tokens

    priced = _price(
        record.model_name,
        Usage(
            input_tokens=input_total,
            cache_read_tokens=record.cache_read_tokens,
            output_tokens=record.output_tokens,
        ),
    )
    if priced is None:
        logger.warning(
            "No genai-prices entry for model %r; skipping cost calc",
            record.model_name,
        )
        return None

    cache_read_cost = _cache_read_cost(
        record.model_name,
        input_total,
        record.cache_read_tokens,
        priced.input_price,
    )
    input_cost = priced.input_price - cache_read_cost
    output_cost = priced.output_price

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


def compute_cost(records: Iterable[UsageRecord]) -> CostBreakdown | None:
    """Aggregate UsageRecords into a CostBreakdown.

    Returns None when no records can be priced (no input, or every model unknown).
    """
    breakdown = CostBreakdown()
    has_any = False
    for record in records:
        per_model = _cost_for_record(record)
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
