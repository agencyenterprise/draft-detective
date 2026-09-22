"""Error inspection must not raise or turn sibling work into request latency."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx
import httpx2
import openai
import pytest

from lib.config.llm_diagnostics import capture_http_error
from lib.config.llm_error_logger import ErrorLoggingCallback, log_embedding_error
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.workflows.error_details import capture_error_details


@pytest.mark.parametrize("error_class", [httpx.ReadTimeout, httpx2.ReadTimeout])
@pytest.mark.parametrize("wrapped", [False, True])
def test_unattached_request_does_not_replace_original_error(
    error_class: type[Exception], wrapped: bool, caplog: pytest.LogCaptureFixture
) -> None:
    error = error_class("original timeout")
    if wrapped:
        outer = RuntimeError("original wrapper")
        outer.__cause__ = error
        error = outer

    assert capture_http_error(error) is None
    ErrorLoggingCallback().on_llm_error(error, run_id=uuid4())
    log_embedding_error(error, caller="test", model="test", provider="openai")
    assert type(error).__name__ in caplog.text
    details = capture_error_details(error)
    assert details.error_type == type(error).__name__
    assert details.llm_metadata is None
    assert details.traceback is not None
    assert "original timeout" in details.traceback


@pytest.mark.asyncio
async def test_delayed_chunk_persistence_preserves_response_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [250.0]
    monkeypatch.setattr("lib.config.llm_error_logger.monotonic", lambda: clock[0])
    response = httpx2.Response(
        500, request=httpx2.Request("POST", "https://example.com/responses")
    )
    response.elapsed = timedelta(seconds=240)
    error = openai.InternalServerError("failed", response=response, body=None)
    failed = asyncio.Event()
    callback = ErrorLoggingCallback()
    run_id = uuid4()
    callback.on_llm_start({}, [], run_id=run_id)

    async def failing_chunk() -> None:
        callback.on_llm_error(error, run_id=run_id)
        failed.set()
        raise error

    async def slow_sibling() -> str:
        await failed.wait()
        clock[0] = 850.0  # Simulate ten more minutes of sibling work.
        return "done"

    _, exceptions = await run_tasks([failing_chunk(), slow_sibling()])
    saved = convert_exceptions_to_workflow_errors("test", exceptions)
    assert saved[0].details is not None
    assert saved[0].details.llm_metadata is not None
    details = saved[0].details.llm_metadata["http_error"]
    assert details["response_elapsed_ms"] == 240000
    assert capture_http_error(error) == details
