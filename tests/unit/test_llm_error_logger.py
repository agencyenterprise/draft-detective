"""Tests for the LLM error logger (ErrorLoggingCallback + log_embedding_error).

Covers:
- 429 detection across openai/anthropic SDKs and via fallback `status_code` attr.
- Distinct `LLM_RATE_LIMIT` vs `LLM_ERROR` prefix selection.
- Per-call metadata captured at `on_chat_model_start` and consumed at
  `on_llm_error`, including agent name from `metadata.langgraph_node`.
- Endpoint discovery from serialized LLM kwargs / fallback to error response.
- Cleanup on `on_llm_end` so the per-call cache stays bounded.
- The `log_embedding_error` helper format.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import anthropic
import httpx
import openai
import pytest

from lib.config.llm_error_logger import (
    ErrorLoggingCallback,
    log_embedding_error,
)
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows.context import ContextSchema

_LOGGER_NAME = "lib.config.llm_error_logger"


def _make_context() -> ContextSchema:
    """Minimal ContextSchema for tests."""
    return ContextSchema(
        project_id="proj-123",
        workflow_run_id="run-456",
        file_artifacts_service=MagicMock(spec=FileArtifactsServiceType),
    )


def _make_response(
    status_code: int, url: str = "https://api.example.com/v1/x"
) -> httpx.Response:
    request = httpx.Request("POST", url)
    return httpx.Response(status_code=status_code, request=request)


def _make_openai_rate_limit_error() -> openai.RateLimitError:
    response = _make_response(429, "https://api.openai.com/v1/chat/completions")
    return openai.RateLimitError(message="rate limited", response=response, body=None)


def _make_anthropic_rate_limit_error() -> anthropic.RateLimitError:
    response = _make_response(429, "https://api.anthropic.com/v1/messages")
    return anthropic.RateLimitError(
        message="rate limited", response=response, body=None
    )


def _make_callback() -> ErrorLoggingCallback:
    return ErrorLoggingCallback(
        workflow_run_id="run-456",
        project_id="proj-123",
    )


def _start_chat_model(
    callback: ErrorLoggingCallback,
    *,
    run_id: UUID,
    node: str = "extract_claims",
    model_name: str = "gpt-5-mini",
    provider: str = "openai",
    base_url: str | None = None,
) -> None:
    """Drive the standard `on_chat_model_start` invocation that LangChain
    fires before every chat-model call. Mirrors the metadata LangChain core
    populates via LangSmithParams, plus LangGraph's `langgraph_node` key."""
    metadata: dict[str, Any] = {
        "ls_model_name": model_name,
        "ls_provider": provider,
        "ls_model_type": "chat",
        "langgraph_node": node,
    }
    serialized: dict[str, Any] = {"id": ["langchain", "ChatOpenAI"], "kwargs": {}}
    if base_url is not None:
        serialized["kwargs"]["openai_api_base"] = base_url
    callback.on_chat_model_start(
        serialized,
        messages=[],
        run_id=run_id,
        metadata=metadata,
        tags=[],
    )


def _last_log_record(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    records = [r for r in caplog.records if r.name == _LOGGER_NAME]
    assert records, "Expected at least one log record from the llm error logger"
    return records[-1]


def test_callback_logs_rate_limit_with_429_prefix(
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback = _make_callback()
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id, node="reference_validator")
    callback.on_llm_error(_make_openai_rate_limit_error(), run_id=run_id)

    record = _last_log_record(caplog)
    assert record.levelno == logging.WARNING
    assert record.message.startswith("LLM_RATE_LIMIT ")
    assert "agent=reference_validator" in record.message
    assert "model=gpt-5-mini" in record.message
    assert "provider=openai" in record.message
    assert "status=429" in record.message
    assert "workflow_run_id=run-456" in record.message
    assert "project_id=proj-123" in record.message


def test_callback_logs_other_errors_with_generic_prefix(
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback = _make_callback()
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id)
    callback.on_llm_error(TimeoutError("read timed out"), run_id=run_id)

    record = _last_log_record(caplog)
    assert record.levelno == logging.ERROR
    assert record.message.startswith("LLM_ERROR ")
    assert "error_type=TimeoutError" in record.message
    assert "status=-" in record.message
    assert 'message="read timed out"' in record.message


def test_callback_detects_anthropic_rate_limit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback = _make_callback()
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(
        callback,
        run_id=run_id,
        model_name="claude-sonnet-4-5",
        provider="anthropic",
    )
    callback.on_llm_error(_make_anthropic_rate_limit_error(), run_id=run_id)

    record = _last_log_record(caplog)
    assert record.message.startswith("LLM_RATE_LIMIT ")
    assert "model=claude-sonnet-4-5" in record.message
    assert "provider=anthropic" in record.message
    assert "status=429" in record.message
    assert "error_type=RateLimitError" in record.message


def test_callback_detects_429_via_status_code_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exception type unknown to us is still recognized as a rate limit
    when it carries `status_code=429`."""

    class _FakeError(Exception):
        status_code = 429

    callback = _make_callback()
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id)
    callback.on_llm_error(_FakeError("throttled"), run_id=run_id)

    record = _last_log_record(caplog)
    assert record.message.startswith("LLM_RATE_LIMIT ")
    assert "status=429" in record.message


def test_callback_includes_endpoint_when_in_serialized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When `serialized.kwargs` carries a base_url, it shows up as endpoint=."""
    callback = _make_callback()
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(
        callback, run_id=run_id, base_url="https://api.openai.com/v1"
    )
    callback.on_llm_error(_make_openai_rate_limit_error(), run_id=run_id)

    record = _last_log_record(caplog)
    assert "endpoint=https://api.openai.com/v1" in record.message


def test_callback_falls_back_to_endpoint_from_error_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When serialized has no base_url, the error's response.request.url
    should be used as the endpoint."""
    callback = _make_callback()
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id, base_url=None)
    callback.on_llm_error(_make_openai_rate_limit_error(), run_id=run_id)

    record = _last_log_record(caplog)
    assert "endpoint=https://api.openai.com/v1/chat/completions" in record.message


def test_callback_omits_endpoint_when_not_discoverable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No `endpoint=` field when nothing in serialized or the error reveals one."""
    callback = _make_callback()
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id, base_url=None)
    # A plain TimeoutError has no response/request — nothing to discover.
    callback.on_llm_error(TimeoutError("nope"), run_id=run_id)

    record = _last_log_record(caplog)
    assert "endpoint=" not in record.message


def test_callback_uses_unknown_when_metadata_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Errors without a preceding on_chat_model_start (e.g. start was missed
    or the call originated outside the graph) still get logged with placeholders
    rather than crashing."""
    callback = _make_callback()
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)

    callback.on_llm_error(TimeoutError("orphan"), run_id=uuid4())

    record = _last_log_record(caplog)
    assert record.message.startswith("LLM_ERROR ")
    assert "agent=unknown" in record.message
    assert "model=unknown" in record.message


def test_callback_releases_metadata_on_llm_end() -> None:
    """on_llm_end clears the per-call cache so it doesn't grow unbounded
    across a long-running workflow."""
    callback = _make_callback()
    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id)
    assert run_id in callback._calls

    callback.on_llm_end(response=MagicMock(), run_id=run_id)
    assert run_id not in callback._calls


def test_callback_releases_metadata_on_llm_error() -> None:
    """on_llm_error also clears the per-call cache (errors and successes both
    terminate the call)."""
    callback = _make_callback()
    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id)
    assert run_id in callback._calls

    callback.on_llm_error(TimeoutError("x"), run_id=run_id)
    assert run_id not in callback._calls


def test_log_embedding_error_helper_format(caplog: pytest.LogCaptureFixture) -> None:
    fake_embeddings = MagicMock(spec=["openai_api_base"])
    fake_embeddings.openai_api_base = "https://api.openai.com/v1"
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    log_embedding_error(
        _make_openai_rate_limit_error(),
        caller="vector_store.index_document",
        model="text-embedding-3-large",
        provider="openai",
        embeddings_client=fake_embeddings,
        context=_make_context(),
    )

    record = _last_log_record(caplog)
    assert record.message.startswith("LLM_RATE_LIMIT ")
    assert "agent=vector_store.index_document" in record.message
    assert "model=text-embedding-3-large" in record.message
    assert "provider=openai" in record.message
    assert "endpoint=https://api.openai.com/v1" in record.message
    assert "status=429" in record.message
    assert "workflow_run_id=run-456" in record.message
    assert "project_id=proj-123" in record.message


def test_log_embedding_error_handles_missing_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """vector_store doesn't currently hold a ContextSchema — log line should
    still be emitted, with workflow_run_id=- and project_id=- placeholders."""
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)

    log_embedding_error(
        TimeoutError("oops"),
        caller="vector_store.is_collection_indexed",
        model="text-embedding-3-large",
        provider="openai",
        embeddings_client=None,
        context=None,
    )

    record = _last_log_record(caplog)
    assert record.message.startswith("LLM_ERROR ")
    assert "workflow_run_id=-" in record.message
    assert "project_id=-" in record.message


def test_message_is_flattened_to_single_line_without_truncation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Multi-line messages are flattened to one line (so each log record stays
    a single grep-friendly line) but the full text is preserved."""
    callback = _make_callback()
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)

    run_id = uuid4()
    _start_chat_model(callback, run_id=run_id)

    long_payload = "x" * 500
    long_message = f"boom\nwith newlines and {long_payload}"
    callback.on_llm_error(RuntimeError(long_message), run_id=run_id)

    record = _last_log_record(caplog)
    # Only one line per log record (newlines flattened to spaces).
    assert "\n" not in record.message
    # Full payload retained — nothing dropped or truncated.
    assert long_payload in record.message
    assert "with newlines and" in record.message
