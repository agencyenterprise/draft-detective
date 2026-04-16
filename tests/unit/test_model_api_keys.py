"""Unit tests for per-model API key support."""

from unittest.mock import MagicMock, patch

from lib.config.llm_models import LLMModel
from lib.config.rate_limiter import hash_api_key
from lib.services.file_artifacts_service.file_artifacts_service_type import FileArtifactsServiceType
from lib.workflows.context import ContextSchema


def _make_context(openai_api_key: str | None = None) -> ContextSchema:
    return ContextSchema(
        openai_api_key=openai_api_key,
        file_artifacts_service=MagicMock(spec=FileArtifactsServiceType),
        project_id="test-project",
    )


class _TestAgent:
    """Minimal LangChainAgent-like object for testing get_init_chat_model_kwargs / get_rate_limiter."""

    name = "Test Agent"
    description = "Test"
    temperature = 0.0
    timeout = 60
    reasoning = None
    output_schema = None
    model = LLMModel(provider="openai", name="gpt-5-mini-2025-08-07")

    def __init__(self, context: ContextSchema):
        self.context = context
        self._llm = None

    from lib.models.agent import LangChainAgent

    get_rate_limiter = LangChainAgent.get_rate_limiter
    get_init_chat_model_kwargs = LangChainAgent.get_init_chat_model_kwargs


def test_model_api_key_used_in_init_kwargs():
    agent = _TestAgent(_make_context())
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        kwargs = agent.get_init_chat_model_kwargs()
    assert kwargs["api_key"] == "sk-model-specific"


def test_model_api_key_takes_priority_over_context_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        kwargs = agent.get_init_chat_model_kwargs()
    assert kwargs["api_key"] == "sk-model-specific"


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


def test_rate_limiter_bucketed_by_model_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {"gpt-5-mini-2025-08-07": "sk-model-specific"}
        limiter = agent.get_rate_limiter()

    from lib.config.rate_limiter import get_rate_limiter as get_rl
    expected = get_rl(hash_api_key("sk-model-specific"))
    assert limiter is expected


def test_rate_limiter_falls_back_to_context_key():
    agent = _TestAgent(_make_context(openai_api_key="sk-context-key"))
    with patch("lib.config.env.config") as mock_config:
        mock_config.MODEL_API_KEYS = {}
        limiter = agent.get_rate_limiter()

    from lib.config.rate_limiter import get_rate_limiter as get_rl
    expected = get_rl(hash_api_key("sk-context-key"))
    assert limiter is expected
