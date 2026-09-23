"""Configuration checks without constructing clients or making model calls."""

import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from lib.config.env import config
from lib.config.llm_models import (
    LLMModel,
    get_default_workflow_model,
    gpt_5_6_terra_model,
)
from lib.models.agent import LangChainAgent


class StubAgent(LangChainAgent):
    model = LLMModel(provider="azure_openai", name="test-deployment")
    temperature = 0.0

    async def ainvoke(self, prompt_kwargs, config=None):
        raise NotImplementedError


def test_azure_client_uses_azure_credentials_not_openai_context(monkeypatch):
    monkeypatch.setattr(config, "MODEL_API_KEYS", {})
    monkeypatch.setattr(config, "AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setattr(config, "AZURE_OPENAI_ENDPOINT", "https://azure.example")
    monkeypatch.setattr(config, "AZURE_OPENAI_API_VERSION", "test-version")
    agent = StubAgent(SimpleNamespace(openai_api_key="openai-test-key"))
    kwargs = agent.get_init_chat_model_kwargs()
    assert kwargs["api_key"] == "azure-test-key"
    assert kwargs["azure_endpoint"] == "https://azure.example"
    assert kwargs["api_version"] == "test-version"
    assert kwargs["model"] == "azure_openai:test-deployment"


def test_explicit_model_key_overrides_azure_default(monkeypatch):
    monkeypatch.setattr(config, "MODEL_API_KEYS", {"test-deployment": "model-test-key"})
    monkeypatch.setattr(config, "AZURE_OPENAI_API_KEY", "azure-test-key")
    assert (
        StubAgent(SimpleNamespace(openai_api_key=None))._resolve_api_key()
        == "model-test-key"
    )


def test_default_model_unchanged_without_eval_override(monkeypatch):
    monkeypatch.delenv("EVAL_WORKFLOW_MODEL", raising=False)
    assert get_default_workflow_model() == gpt_5_6_terra_model
    monkeypatch.setenv("EVAL_WORKFLOW_MODEL", "openai/test-model")
    assert get_default_workflow_model() == LLMModel(
        provider="openai", name="test-model"
    )


def test_disabled_mcp_skips_oauth_setup(monkeypatch):
    import fastmcp
    from lib.api import mcp_auth

    auth = Mock(side_effect=AssertionError("OAuth setup should not run"))
    factory = Mock()
    monkeypatch.setattr(config, "MCP_ENABLED", False)
    monkeypatch.setattr(mcp_auth, "create_mcp_auth", auth)
    monkeypatch.setattr(fastmcp, "FastMCP", factory)
    path = Path(__file__).resolve().parents[3] / "lib/api/mcp/instance.py"
    namespace = runpy.run_path(str(path))
    assert namespace["mcp_auth"] is None
    auth.assert_not_called()
    assert factory.call_args.kwargs["auth"] is None
