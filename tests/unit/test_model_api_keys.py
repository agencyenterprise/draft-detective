"""Unit tests for per-model API key support."""

from unittest.mock import MagicMock, patch

from lib.config.env import config, openai_header_kwargs
from lib.config.llm_models import LLMModel
from lib.config.rate_limiter import get_rate_limiter as get_rl
from lib.config.rate_limiter import hash_api_key
from lib.models.agent import LangChainAgent
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows.context import ContextSchema


def _make_context(openai_api_key: str | None = None) -> ContextSchema:
    return ContextSchema(
        openai_api_key=openai_api_key,
        file_artifacts_service=MagicMock(spec=FileArtifactsServiceType),
        project_id="test-project",
    )


class _TestAgent(LangChainAgent):
    """Minimal LangChainAgent subclass for testing API key resolution."""

    name = "Test Agent"
    description = "Test"
    timeout = 60
    reasoning = None
    output_schema = None
    model = LLMModel(provider="openai", name="gpt-5-mini-2025-08-07")

    async def ainvoke(self, prompt_kwargs, config=None):  # type: ignore[override]
        raise NotImplementedError


def test_model_api_key_used_in_init_kwargs():
    agent = _TestAgent(_make_context())
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        kwargs = agent.get_init_chat_model_kwargs()
    assert kwargs["api_key"] == "sk-model-specific"


def test_context_key_takes_priority_over_model_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        kwargs = agent.get_init_chat_model_kwargs()
    assert kwargs["api_key"] == "sk-context-key"


def test_context_key_used_when_no_model_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {}
        kwargs = agent.get_init_chat_model_kwargs()
    assert kwargs["api_key"] == "sk-context-key"


def test_no_api_key_in_kwargs_when_neither_set():
    agent = _TestAgent(_make_context())
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {}
        kwargs = agent.get_init_chat_model_kwargs()
    assert "api_key" not in kwargs


def test_rate_limiter_uses_model_key_when_no_context_key():
    agent = _TestAgent(_make_context())
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        limiter = agent.get_rate_limiter()

    expected = get_rl(hash_api_key("sk-model-specific"))
    assert limiter is expected


def test_rate_limiter_prefers_context_key_over_model_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        limiter = agent.get_rate_limiter()

    expected = get_rl(hash_api_key("sk-context-key"))
    assert limiter is expected


def test_rate_limiter_falls_back_to_context_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {}
        limiter = agent.get_rate_limiter()

    expected = get_rl(hash_api_key("sk-context-key"))
    assert limiter is expected


class TestKeyHeader:
    """OPENAI_API_KEY_HEADER: a gateway that reads the key from a header of its own."""

    def test_agent_sends_its_key_in_the_named_header(self, monkeypatch):
        monkeypatch.setattr(config, "OPENAI_API_KEY_HEADER", "api-key")
        agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))

        kwargs = agent.get_init_chat_model_kwargs()

        assert kwargs["default_headers"] == {"api-key": "sk-context-key"}

    def test_falls_back_to_the_server_key(self, monkeypatch):
        monkeypatch.setattr(config, "OPENAI_API_KEY_HEADER", "api-key")
        monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-server")

        assert openai_header_kwargs(None) == {
            "default_headers": {"api-key": "sk-server"}
        }

    def test_no_header_unless_configured(self, monkeypatch):
        monkeypatch.setattr(config, "OPENAI_API_KEY_HEADER", None)
        agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))

        assert "default_headers" not in agent.get_init_chat_model_kwargs()

    def test_no_header_for_other_providers(self, monkeypatch):
        monkeypatch.setattr(config, "OPENAI_API_KEY_HEADER", "api-key")
        monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-server")
        agent = _TestAgent(_make_context())
        agent.model = LLMModel(provider="anthropic", name="claude-sonnet-5-5")

        assert "default_headers" not in agent.get_init_chat_model_kwargs()
