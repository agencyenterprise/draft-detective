from decimal import Decimal

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from lib.config.llm_models import ALL_MODELS
from lib.services.workflow_cost import pricing
from lib.services.workflow_cost.breakdown import UsageRecord
from lib.services.workflow_cost.extractor import walk_state_for_usage
from lib.services.workflow_cost.pricing import compute_cost

CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
OPENAI_MODEL = "gpt-5.6-terra"


def _record(**kwargs) -> UsageRecord:
    kwargs.setdefault("model_name", OPENAI_MODEL)
    return UsageRecord(**kwargs)


def _ai_message(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    model: str = CLAUDE_MODEL,
) -> AIMessage:
    # On Anthropic, usage_metadata.input_tokens *includes* cache reads, so the
    # test fixture mirrors that.
    return AIMessage(
        content="",
        response_metadata={"model_name": model},
        usage_metadata={
            "input_tokens": input_tokens + cache_read,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + cache_read + output_tokens,
            "input_token_details": {"cache_read": cache_read},
        },
    )


def test_extracts_usage_from_flat_message_list():
    state = {
        "messages": [
            HumanMessage(content="hi"),
            _ai_message(input_tokens=100, output_tokens=50),
        ]
    }
    records = walk_state_for_usage(state)
    assert len(records) == 1
    assert records[0].input_tokens == 100
    assert records[0].output_tokens == 50
    assert records[0].model_name == CLAUDE_MODEL


def test_extracts_usage_from_serialized_dict_form():
    """State loaded from checkpointer may have messages as plain dicts."""
    state = {
        "messages": [
            {
                "type": "ai",
                "content": "",
                "response_metadata": {"model_name": CLAUDE_MODEL},
                "usage_metadata": {
                    "input_tokens": 200,
                    "output_tokens": 80,
                    "input_token_details": {"cache_read": 0, "cache_creation": 0},
                },
            }
        ]
    }
    records = walk_state_for_usage(state)
    assert len(records) == 1
    assert records[0].input_tokens == 200
    assert records[0].output_tokens == 80


def test_walks_nested_messages_in_substate():
    state = {
        "validators": {
            "claim_1": {"messages": [_ai_message(input_tokens=10, output_tokens=5)]},
            "claim_2": {"messages": [_ai_message(input_tokens=20, output_tokens=8)]},
        }
    }
    records = walk_state_for_usage(state)
    assert len(records) == 2
    assert sum(r.input_tokens for r in records) == 30
    assert sum(r.output_tokens for r in records) == 13


def test_skips_messages_without_usage_metadata():
    state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
    assert walk_state_for_usage(state) == []


def test_skips_message_with_unknown_model():
    """AIMessage without response_metadata.model_name is skipped (no model to price)."""
    msg = AIMessage(
        content="",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_token_details": {},
        },
    )
    assert walk_state_for_usage({"messages": [msg]}) == []


def test_walks_pydantic_state_model():
    class State(BaseModel):
        messages: list = []
        other: dict = {}

    state = State(
        messages=[_ai_message(input_tokens=42, output_tokens=7)],
        other={"messages": [_ai_message(input_tokens=8, output_tokens=3)]},
    )
    records = walk_state_for_usage(state)
    assert len(records) == 2
    assert sum(r.input_tokens for r in records) == 50


def test_separates_cache_read_from_input():
    msg = _ai_message(input_tokens=100, output_tokens=20, cache_read=500)
    records = walk_state_for_usage({"messages": [msg]})
    assert len(records) == 1
    r = records[0]
    assert r.input_tokens == 100
    assert r.cache_read_tokens == 500


# --- pricing -------------------------------------------------------------
#
# Rates come from the `genai-prices` dataset bundled in the package, so these
# assert relationships and resolution rather than dollar figures: a dependency
# bump that changes a published price must not fail the suite.


def test_compute_cost_returns_none_when_empty():
    assert compute_cost([]) is None


def test_compute_cost_known_model():
    records = walk_state_for_usage(
        {
            "messages": [
                _ai_message(input_tokens=1000, output_tokens=500, cache_read=2000)
            ]
        }
    )
    breakdown = compute_cost(records)
    assert breakdown is not None
    assert breakdown.total_input_tokens == 1000
    assert breakdown.total_output_tokens == 500
    assert breakdown.total_cache_read_tokens == 2000
    assert breakdown.total_cost_usd > 0
    assert CLAUDE_MODEL in breakdown.by_model


def test_component_costs_sum_to_the_total():
    """The UI itemises input/output/cache read, so the parts must make the whole."""
    breakdown = compute_cost(
        [_record(input_tokens=40_000, output_tokens=5_000, cache_read_tokens=300_000)]
    )
    assert breakdown is not None
    assert (
        breakdown.input_cost_usd
        + breakdown.output_cost_usd
        + breakdown.cache_read_cost_usd
        == breakdown.total_cost_usd
    )
    assert breakdown.input_cost_usd > 0
    assert breakdown.cache_read_cost_usd > 0


def test_cache_reads_cost_less_than_plain_input():
    cached = compute_cost([_record(input_tokens=0, cache_read_tokens=100_000)])
    uncached = compute_cost([_record(input_tokens=100_000, cache_read_tokens=0)])
    assert cached is not None and uncached is not None
    assert 0 < cached.total_cost_usd < uncached.total_cost_usd


def test_compute_cost_unknown_model_skipped():
    records = [_record(model_name="made-up-model-xyz", input_tokens=100)]
    assert compute_cost(records) is None


def test_compute_cost_prices_dated_snapshot_as_its_alias():
    """The Azure gateway reports `gpt-5.6-terra-2026-07-09-global-aaif`."""
    usage = dict(input_tokens=100_000, output_tokens=50_000, cache_read_tokens=20_000)
    snapshot = compute_cost(
        [_record(model_name=f"{OPENAI_MODEL}-2026-07-09-global-aaif", **usage)]
    )
    alias = compute_cost([_record(model_name=OPENAI_MODEL, **usage)])
    assert snapshot is not None and alias is not None
    assert snapshot.total_cost_usd == alias.total_cost_usd
    # The breakdown keeps the name the provider actually reported.
    assert list(snapshot.by_model) == [f"{OPENAI_MODEL}-2026-07-09-global-aaif"]


def test_compute_cost_prices_bare_dated_snapshot():
    snapshot = compute_cost(
        [_record(model_name=f"{OPENAI_MODEL}-2026-07-09", input_tokens=10_000)]
    )
    alias = compute_cost([_record(model_name=OPENAI_MODEL, input_tokens=10_000)])
    assert snapshot is not None and alias is not None
    assert snapshot.total_cost_usd == alias.total_cost_usd


def test_compute_cost_does_not_price_undated_variant_as_base_model():
    """A `-mini` is a different model, not a snapshot; it must stay unpriced."""
    assert compute_cost([_record(model_name=f"{OPENAI_MODEL}-mini")]) is None


def test_compute_cost_aggregates_multiple_models():
    state = {
        "messages": [
            _ai_message(input_tokens=100, output_tokens=50, model=CLAUDE_MODEL),
            _ai_message(input_tokens=200, output_tokens=80, model="gpt-4o-2024-08-06"),
        ]
    }
    breakdown = compute_cost(walk_state_for_usage(state))
    assert breakdown is not None
    assert len(breakdown.by_model) == 2
    assert breakdown.total_input_tokens == 300
    assert breakdown.total_output_tokens == 130
    assert breakdown.request_count == 2
    assert breakdown.by_model[CLAUDE_MODEL].request_count == 1
    assert breakdown.by_model["gpt-4o-2024-08-06"].request_count == 1
    assert breakdown.total_cost_usd == sum(
        m.total_cost_usd for m in breakdown.by_model.values()
    )


def test_unpriced_model_does_not_sink_the_run():
    """One unknown model must not discard the cost of the models alongside it."""
    breakdown = compute_cost(
        [
            _record(model_name="made-up-model-xyz", input_tokens=1_000),
            _record(model_name=OPENAI_MODEL, input_tokens=1_000),
        ]
    )
    assert breakdown is not None
    assert list(breakdown.by_model) == [OPENAI_MODEL]
    assert breakdown.request_count == 1


def test_every_model_this_codebase_can_select_is_priced():
    """The gap that made cost vanish on the RAND deployment: no rates for our models."""
    unpriced = [
        model.name
        for model in ALL_MODELS.values()
        if compute_cost([_record(model_name=model.name, input_tokens=1_000)]) is None
    ]
    assert unpriced == []


def test_costs_stay_decimal():
    """Money must not become float on the way through pricing."""
    breakdown = compute_cost([_record(input_tokens=1_000, cache_read_tokens=500)])
    assert breakdown is not None
    assert isinstance(breakdown.total_cost_usd, Decimal)
    assert isinstance(breakdown.cache_read_cost_usd, Decimal)


def test_unknown_model_warns_once_per_name(caplog):
    """A run with many records for one unpriceable model must log once, not once
    per record: the reverse buried a production log under ~1,850 identical lines."""
    pricing._resolve.cache_clear()
    records = [_record(model_name="made-up-model-xyz", input_tokens=100)] * 50
    with caplog.at_level("WARNING", logger=pricing.__name__):
        assert compute_cost(records) is None
    warnings = [r for r in caplog.records if "made-up-model-xyz" in r.getMessage()]
    assert len(warnings) == 1
