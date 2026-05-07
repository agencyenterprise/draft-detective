import re
from decimal import Decimal
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from lib.services.workflow_cost import pricing
from lib.services.workflow_cost.extractor import walk_state_for_usage
from lib.services.workflow_cost.pricing import compute_cost


CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


def _fake_model(name: str, *, input_price: float, output_price: float, cache_read_price: float) -> object:
    """Build a Langfuse-shaped model object with a regex pattern matching `name` exactly."""
    return SimpleNamespace(
        model_name=name,
        match_pattern=f"(?i)^{re.escape(name)}$",
        prices={
            "input": SimpleNamespace(price=input_price),
            "output": SimpleNamespace(price=output_price),
            "input_cache_read": SimpleNamespace(price=cache_read_price),
        },
    )


@pytest.fixture(autouse=True)
def _stub_models_cache(monkeypatch):
    """Bypass the Langfuse network fetch by populating the price cache with fixtures."""
    fakes = [
        _fake_model(CLAUDE_MODEL, input_price=3e-6, output_price=1.5e-5, cache_read_price=3e-7),
        _fake_model("gpt-4o-2024-08-06", input_price=2.5e-6, output_price=1e-5, cache_read_price=1.25e-6),
    ]
    compiled = [(re.compile(m.match_pattern), m) for m in fakes]
    monkeypatch.setattr(pricing, "_MODELS_CACHE", compiled)
    yield
    monkeypatch.setattr(pricing, "_MODELS_CACHE", None)


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


@pytest.mark.asyncio
async def test_compute_cost_returns_none_when_empty():
    assert await compute_cost([]) is None


@pytest.mark.asyncio
async def test_compute_cost_known_model():
    state = {
        "messages": [
            _ai_message(input_tokens=1000, output_tokens=500, cache_read=2000)
        ]
    }
    records = walk_state_for_usage(state)
    breakdown = await compute_cost(records)
    assert breakdown is not None
    expected_input = Decimal("3e-6") * 1000
    expected_output = Decimal("1.5e-5") * 500
    expected_cache_read = Decimal("3e-7") * 2000
    expected_total = expected_input + expected_output + expected_cache_read
    assert breakdown.total_cost_usd == expected_total
    assert breakdown.total_input_tokens == 1000
    assert breakdown.total_output_tokens == 500
    assert breakdown.total_cache_read_tokens == 2000
    assert CLAUDE_MODEL in breakdown.by_model


@pytest.mark.asyncio
async def test_compute_cost_unknown_model_skipped():
    msg = AIMessage(
        content="",
        response_metadata={"model_name": "made-up-model-xyz"},
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_token_details": {},
        },
    )
    records = walk_state_for_usage({"messages": [msg]})
    assert len(records) == 1
    assert await compute_cost(records) is None


@pytest.mark.asyncio
async def test_compute_cost_aggregates_multiple_models():
    state = {
        "messages": [
            _ai_message(input_tokens=100, output_tokens=50, model=CLAUDE_MODEL),
            _ai_message(
                input_tokens=200, output_tokens=80, model="gpt-4o-2024-08-06"
            ),
        ]
    }
    records = walk_state_for_usage(state)
    breakdown = await compute_cost(records)
    assert breakdown is not None
    assert len(breakdown.by_model) == 2
    assert breakdown.total_input_tokens == 300
    assert breakdown.total_output_tokens == 130
