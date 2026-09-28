"""Tests for forwarding Inspect's --model to the backend and checking the run used it."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from evals_inspectai.common import model_override
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.model_override import (
    check_model_used,
    is_model,
    note_served_models,
    output_model_name,
    requested_model,
)


def _active(name: str) -> Any:
    model = MagicMock()
    model.__str__.return_value = name  # type: ignore[attr-defined]
    return patch.object(model_override, "get_model", return_value=model)


def _run_detail(recorded: str | None, served: list[str]) -> dict[str, Any]:
    return {
        "run": {"id": "run-1", "model": recorded},
        "cost": {"by_model": {name: {} for name in served}},
    }


def test_no_model_keeps_the_agents_own():
    with _active("none/none"):
        assert requested_model() is None


@pytest.mark.parametrize(
    "inspect_name, langchain_name",
    [
        ("openai/gpt-5.6-sol", "openai:gpt-5.6-sol"),
        ("anthropic/claude-opus-5-5", "anthropic:claude-opus-5-5"),
        ("google/gemini-2.5-flash-lite", "google_genai:gemini-2.5-flash-lite"),
    ],
)
def test_model_is_forwarded_as_its_langchain_name(inspect_name: str, langchain_name: str):
    with _active(inspect_name):
        assert requested_model() == langchain_name


def test_outside_an_eval_nothing_is_forwarded():
    with patch.object(model_override, "get_model", side_effect=ValueError("no model")):
        assert requested_model() is None


def test_run_on_the_requested_model_passes():
    with _active("openai/gpt-5.6-sol"):
        check_model_used(_run_detail("openai:gpt-5.6-sol", ["gpt-5.6-sol-2026-08-01"]))


def test_run_started_without_the_override_fails():
    with _active("openai/gpt-5.6-sol"), pytest.raises(WorkflowCompletionError, match="started with"):
        check_model_used(_run_detail(None, ["gpt-5.6-terra"]))


def test_run_served_by_another_model_fails():
    with _active("openai/gpt-5.6-sol"), pytest.raises(WorkflowCompletionError, match="served by"):
        check_model_used(_run_detail("openai:gpt-5.6-sol", ["gpt-5.6-sol", "gpt-5.6-terra"]))


def test_without_model_nothing_is_checked():
    with _active("none/none"):
        check_model_used(_run_detail(None, ["gpt-5.6-terra"]))


def test_output_model_is_what_served_the_run():
    with _active("none/none"):
        assert output_model_name(_run_detail(None, ["gpt-5.6-terra"])) == "gpt-5.6-terra"
        assert output_model_name(_run_detail(None, [])) == "api"
    with _active("openai/gpt-5.6-sol"):
        assert output_model_name(_run_detail("openai:gpt-5.6-sol", [])) == "openai:gpt-5.6-sol"


@pytest.mark.parametrize(
    "served, name, same",
    [
        ("gpt-5.6-sol", "gpt-5.6-sol", True),
        ("gpt-5.6-sol-2026-08-01", "gpt-5.6-sol", True),
        ("gpt-5.6-terra-2026-07-09-global-aaif", "gpt-5.6-terra", True),
        ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5", True),
        ("gpt-5.6-sol-mini", "gpt-5.6-sol", False),
        ("gpt-5.6-sol-mini-2026-08-01", "gpt-5.6-sol", False),
        ("gpt-5.6-sol-mini-2026-08-01-global-aaif", "gpt-5.6-sol", False),
        ("gpt-5.6-solar", "gpt-5.6-sol", False),
    ],
)
def test_a_model_matches_itself_or_its_dated_release(served: str, name: str, same: bool):
    assert is_model(served, name) is same


def test_a_model_with_a_longer_name_fails_the_check():
    with _active("openai/gpt-5.6-sol"), pytest.raises(WorkflowCompletionError, match="served by"):
        check_model_used(_run_detail("openai:gpt-5.6-sol", ["gpt-5.6-sol-mini"]))


def test_an_unpriced_model_in_the_replies_still_fails_the_check():
    detail = _run_detail("openai:gpt-5.6-sol", ["gpt-5.6-sol"])
    detail["state"] = {
        "chunks": [
            {"messages": [
                {"type": "human", "content": "hi"},
                {
                    "type": "ai",
                    "usage_metadata": {"input_tokens": 1},
                    "response_metadata": {"model_name": "some-unpriced-model"},
                },
            ]}
        ]
    }
    with _active("openai/gpt-5.6-sol"), pytest.raises(WorkflowCompletionError, match="some-unpriced-model"):
        check_model_used(detail)


def test_the_output_model_survives_the_replies_moving_to_the_transcript():
    detail = _run_detail("openai:gpt-5.6-sol", [])
    replies = [
        {
            "type": "ai",
            "usage_metadata": {"input_tokens": 1},
            "response_metadata": {"model_name": "some-unpriced-model"},
        }
    ]
    detail["state"] = {"messages": replies}
    note_served_models(detail)
    detail["state"].pop("messages")  # what surface_conversations does
    with _active("openai/gpt-5.6-sol"):
        assert output_model_name(detail) == "some-unpriced-model"
