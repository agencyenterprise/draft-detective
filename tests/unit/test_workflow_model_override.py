"""Unit tests for running a workflow's agents on a model named by the start request."""

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from lib.api.services import workflow_start_checks
from lib.api.services.workflow_start_checks import assert_model_override_allowed
from lib.config.llm_models import (
    LLMModel,
    gpt_5_6_sol_model,
    gpt_5_6_terra_model,
    web_search_tool,
)
from lib.models.agent import LangChainAgent, ReasoningDict
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows import runner
from lib.workflows.context import ContextSchema
from lib.workflows.models import WorkflowRunType
from lib.workflows.runner import create_context

# Overrides accept any provider, so the non-OpenAI branches need models of their own.
CLAUDE_MODEL = LLMModel(provider="anthropic", name="claude-sonnet-4-5-20250929")
GEMINI_MODEL = LLMModel(provider="google_genai", name="gemini-2.5-flash-lite")


def _context(model_override: LLMModel | None = None) -> ContextSchema:
    return ContextSchema(
        file_artifacts_service=MagicMock(spec=FileArtifactsServiceType),
        project_id="test-project",
        model_override=model_override,
    )


class _TerraAgent(LangChainAgent):
    name = "Test Agent"
    description = "Test"
    model = gpt_5_6_terra_model

    async def ainvoke(self, prompt_kwargs: dict, config: Any = None) -> Any:
        raise NotImplementedError


@pytest.mark.parametrize("model", [gpt_5_6_sol_model, CLAUDE_MODEL])
def test_model_name_round_trips(model: LLMModel):
    assert LLMModel.from_model_name(model.model_name) == model


def test_model_name_without_a_provider_parses_to_an_empty_one():
    assert LLMModel.from_model_name("gpt-5.6-sol") == LLMModel(
        provider="", name="gpt-5.6-sol"
    )


def test_no_override_is_always_allowed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        workflow_start_checks.env_config, "ALLOW_WORKFLOW_MODEL_OVERRIDE", False
    )
    assert_model_override_allowed(None)


def test_override_is_refused_when_the_server_does_not_allow_it(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workflow_start_checks.env_config, "ALLOW_WORKFLOW_MODEL_OVERRIDE", False
    )
    with pytest.raises(HTTPException) as exc:
        assert_model_override_allowed("openai:gpt-5.6-sol")
    assert exc.value.status_code == 422
    assert "ALLOW_WORKFLOW_MODEL_OVERRIDE" in exc.value.detail


@pytest.mark.parametrize(
    "name", ["openai:gpt-5.6-sol", "anthropic:claude-opus-5-5", "openai:gpt-99"]
)
def test_any_model_is_accepted_when_overrides_are_allowed(
    monkeypatch: pytest.MonkeyPatch, name: str
):
    monkeypatch.setattr(
        workflow_start_checks.env_config, "ALLOW_WORKFLOW_MODEL_OVERRIDE", True
    )
    assert_model_override_allowed(name)


@pytest.mark.parametrize("name", ["gpt-5.6-sol", ":gpt-5.6-sol", "openai:"])
def test_a_model_without_its_provider_is_refused(
    monkeypatch: pytest.MonkeyPatch, name: str
):
    monkeypatch.setattr(
        workflow_start_checks.env_config, "ALLOW_WORKFLOW_MODEL_OVERRIDE", True
    )
    with pytest.raises(HTTPException) as exc:
        assert_model_override_allowed(name)
    assert exc.value.status_code == 422
    assert "must name its provider" in exc.value.detail


def test_agent_runs_on_the_override_without_changing_its_class():
    agent = _TerraAgent(_context(gpt_5_6_sol_model))
    assert agent.model == gpt_5_6_sol_model
    assert agent.get_init_chat_model_kwargs()["model"] == "openai:gpt-5.6-sol"
    assert _TerraAgent.model == gpt_5_6_terra_model
    assert _TerraAgent(_context()).model == gpt_5_6_terra_model


REASONING: ReasoningDict = {"effort": "medium", "summary": "auto"}


def _kwargs(model: LLMModel | None, reasoning: ReasoningDict | None) -> dict:
    agent = _TerraAgent(_context(model))
    agent.reasoning = reasoning
    return agent.get_init_chat_model_kwargs()


def test_openai_gets_its_reasoning_and_no_temperature():
    kwargs = _kwargs(None, REASONING)
    assert kwargs["reasoning"] == REASONING
    assert "temperature" not in kwargs
    assert "temperature" not in _kwargs(None, None)


def test_claude_thinks_adaptively_at_the_agents_effort():
    kwargs = _kwargs(CLAUDE_MODEL, {"effort": "high", "summary": "auto"})
    assert kwargs["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert kwargs["effort"] == "high"
    assert "temperature" not in kwargs and "reasoning" not in kwargs


def test_claude_without_reasoning_does_not_think():
    kwargs = _kwargs(CLAUDE_MODEL, None)
    assert "thinking" not in kwargs and "effort" not in kwargs
    assert "temperature" not in kwargs


def test_other_providers_run_without_reasoning():
    kwargs = _kwargs(GEMINI_MODEL, REASONING)
    assert "reasoning" not in kwargs and "thinking" not in kwargs
    assert "temperature" not in kwargs


def test_each_provider_gets_its_own_web_search_declaration():
    assert web_search_tool(gpt_5_6_sol_model) == {"type": "web_search"}
    assert web_search_tool(CLAUDE_MODEL) == {
        "type": "web_search_20250305",
        "name": "web_search",
    }
    assert web_search_tool(GEMINI_MODEL) == {"google_search": {}}


@pytest.mark.parametrize("provider", ["", "mistralai"])
def test_web_search_is_refused_for_a_provider_without_a_declaration(provider: str):
    with pytest.raises(ValueError, match="No web-search tool"):
        web_search_tool(LLMModel(provider=provider, name="some-model"))


def test_create_context_resolves_the_configured_model():
    config = MagicMock()
    config.openai_api_key = "sk-test"
    config.project_id = "test-project"
    config.model = "openai:gpt-5.6-sol"
    with (
        patch("lib.workflows.runner.VectorStoreService", return_value=None),
        patch(
            "lib.workflows.runner.FileArtifactsService",
            return_value=MagicMock(spec=FileArtifactsServiceType),
        ),
    ):
        context = create_context(config, revision=1)
        assert context.model_override == gpt_5_6_sol_model

        config.model = None
        assert create_context(config, revision=1).model_override is None


@pytest.mark.asyncio
async def test_the_job_runs_a_run_on_the_model_its_row_records():
    """A joined or gate-released run runs on the model it was created with."""
    run = WorkflowRun(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
        langgraph_thread_id="thread",
        status=WorkflowRunStatus.RUNNING,
        model="openai:gpt-5.6-sol",
        config_json={
            "type": WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2.value,
            "project_id": str(uuid.uuid4()),
            "model": None,
        },
    )

    config = await runner._config_of(run)

    assert config.model == "openai:gpt-5.6-sol"
    assert config.openai_api_key is None
