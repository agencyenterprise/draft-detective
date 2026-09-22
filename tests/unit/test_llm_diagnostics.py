"""HTTP diagnostics stay useful through SDK wrappers without copying secrets."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx2
import openai
import pytest

from lib.config.llm_diagnostics import capture_http_error, response_diagnostics
from lib.config.llm_http_logging import instrument_openai_http
from lib.workflows.error_details import build_workflow_error


def make_error():
    response = httpx2.Response(
        500,
        request=httpx2.Request(
            "POST",
            "https://user:secret@gateway.example/responses?api-key=secret",
            headers={
                "Authorization": "Bearer secret",
                "x-client-request-id": "client-1",
            },
        ),
        headers={
            "X-Request-ID": "req-1",
            "apim-request-id": "apim-1",
            "x-ms-request-id": "azure-1",
            "openai-processing-ms": "239900",
            "set-cookie": "secret",
            "authorization": "secret",
        },
        json={
            "statusCode": 500,
            "message": "Internal server error",
            "activityId": "activity-1",
            "input": "private document",
        },
    )
    return openai.InternalServerError(
        "Internal server error", response=response, body=response.json()
    )


def test_gateway_diagnostics_survive_wrapping_and_persistence():
    error = make_error()
    wrapper = RuntimeError("wrapped")
    wrapper.__cause__ = error
    details = capture_http_error(wrapper)
    assert details["status_code"] == 500
    assert details["request_id"] == "req-1"
    assert details["response_headers"]["apim-request-id"] == "apim-1"
    assert details["response_error"]["activityId"] == "activity-1"
    assert details["client_request_id"] == "client-1"
    assert details["endpoint"] == "https://gateway.example/responses"
    assert "secret" not in json.dumps(details)
    assert "private document" not in json.dumps(details)
    saved = build_workflow_error("check_abbreviations", wrapper)
    restored = type(saved).model_validate_json(saved.model_dump_json())
    assert restored.details.llm_metadata["http_error"] == details


def test_openai_fields_nested_body_and_bounded_values():
    error = make_error()
    error.body = {
        "error": {
            "code": "server_error",
            "type": "api_error",
            "param": "input",
            "message": "x" * 10000,
            "input": "secret",
        }
    }
    result = capture_http_error(error)
    fields = result["response_error"]["error"]
    assert fields["code"] == "server_error"
    assert fields["type"] == "api_error"
    assert fields["param"] == "input"
    assert len(fields["message"]) < 2100
    assert "input" not in fields


def test_missing_html_and_unread_bodies_and_cyclic_exceptions():
    assert capture_http_error(ValueError("no HTTP details")) is None
    response = httpx2.Response(502, text="<html>private proxy details</html>")
    assert response_diagnostics(response) == {"status_code": 502}
    response = httpx2.Response(500, stream=httpx2.ByteStream(b"not read"))
    assert response_diagnostics(response) == {"status_code": 500}
    wrapper = RuntimeError("cycle")
    error = make_error()
    wrapper.__cause__ = error
    error.__cause__ = wrapper
    assert capture_http_error(wrapper)["status_code"] == 500


def test_sync_sdk_retries_log_each_attempt_and_preserve_error(caplog):
    caplog.set_level("INFO", logger="lib.config.llm_http_logging")
    requests = []

    def handle(request):
        requests.append(request)
        return httpx2.Response(
            500,
            headers={"x-request-id": f"req-{len(requests)}"},
            json={"activityId": "activity-1"},
        )

    with httpx2.Client(transport=httpx2.MockTransport(handle)) as http:
        client = openai.OpenAI(
            api_key="test-key",
            base_url="https://example.com",
            http_client=http,
            max_retries=1,
        )
        model = SimpleNamespace(root_client=client)
        instrument_openai_http(model)
        instrument_openai_http(model)  # shared/cached clients must not duplicate hooks
        with (
            patch("openai._base_client.time.sleep"),
            patch(
                "lib.config.llm_http_logging.monotonic", side_effect=[0, 240, 241, 481]
            ),
        ):
            with pytest.raises(openai.InternalServerError) as caught:
                client.responses.create(model="test", input="private document")
        details = capture_http_error(caught.value)
        assert details["response_headers_elapsed_ms"] == 240000
        assert details["attempt"] == 2
        assert details["response_headers"]["x-request-id"] == "req-2"
    records = [
        r.message for r in caplog.records if r.message.startswith("LLM_HTTP_ATTEMPT ")
    ]
    assert len(records) == 2
    assert json.loads(records[0].split(" ", 1)[1])["attempt"] == 1
    assert len({r.headers["x-client-request-id"] for r in requests}) == 2
    assert "private document" not in " ".join(records)
    assert "test-key" not in " ".join(records)


@pytest.mark.asyncio
async def test_async_sdk_retry_then_success_and_stream_not_consumed(caplog):
    caplog.set_level("INFO", logger="lib.config.llm_http_logging")
    attempts = []

    async def handle(request):
        attempts.append(request)
        status = 500 if len(attempts) == 1 else 200
        return httpx2.Response(
            status,
            headers={"x-request-id": f"req-{len(attempts)}"},
            json={"id": "resp-1", "output": []},
        )

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as http:
        client = openai.AsyncOpenAI(
            api_key="test-key",
            base_url="https://example.com",
            http_client=http,
            max_retries=1,
        )
        instrument_openai_http(SimpleNamespace(root_async_client=client))
        with patch("openai._base_client.anyio.sleep"):
            result = await client.responses.create(model="test", input="private")
        assert result.id == "resp-1"
        # Running the response hook alone must not consume a streaming body.
        response = httpx2.Response(
            200, request=attempts[-1], stream=httpx2.ByteStream(b"event: data")
        )
        await http.event_hooks["response"][0](response)
        assert not response.is_stream_consumed
    records = [
        r.message for r in caplog.records if r.message.startswith("LLM_HTTP_ATTEMPT ")
    ]
    assert [json.loads(r.split(" ", 1)[1])["status_code"] for r in records] == [
        500,
        200,
        200,
    ]


@pytest.mark.asyncio
async def test_langchain_agent_error_reaches_logs_and_saved_details(caplog):
    from langchain_openai import ChatOpenAI
    from lib.agents.abbreviation_checker import AbbreviationCheckerAgent
    from lib.config.llm_error_logger import ErrorLoggingCallback

    caplog.set_level("INFO")

    async def handle(request):
        return httpx2.Response(
            500,
            headers={"x-request-id": "req-langchain"},
            json={
                "statusCode": 500,
                "message": "Internal server error",
                "activityId": "gateway-activity",
            },
        )

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as http:
        model = ChatOpenAI(
            model="test",
            api_key="test-key",
            base_url="https://example.com",
            http_async_client=http,
            max_retries=0,
        )
        agent = AbbreviationCheckerAgent(SimpleNamespace(openai_api_key="test-key"))
        with patch("lib.models.agent.init_chat_model", return_value=model):
            assert agent.create_llm() is model
        callback = ErrorLoggingCallback(
            workflow_run_id="workflow-1", project_id="project-1"
        )
        with pytest.raises(Exception) as caught:
            await model.ainvoke("private document", config={"callbacks": [callback]})
        details = capture_http_error(caught.value)
        assert details["response_headers"]["x-request-id"] == "req-langchain"
        assert details["response_error"]["activityId"] == "gateway-activity"
        assert "response_headers_elapsed_ms" in details
        saved = build_workflow_error("check_abbreviations", caught.value)
        assert saved.details.llm_metadata["http_error"] == details
        line = next(
            r.message for r in caplog.records if r.message.startswith("LLM_ERROR ")
        )
        diagnostics = json.loads(line.split("diagnostics=", 1)[1])
        assert diagnostics["request_id"] == "req-langchain"
        assert diagnostics["call_elapsed_ms"] >= 0
        assert "workflow_run_id=workflow-1" in line
        assert "private document" not in line
        assert "test-key" not in line
        await model.root_async_client.close()
        model.root_client.close()


@pytest.mark.asyncio
async def test_timeout_preserves_client_id_and_elapsed_time():
    async def handle(request):
        raise httpx2.ReadTimeout("timed out", request=request)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as http:
        client = openai.AsyncOpenAI(
            api_key="test-key",
            base_url="https://example.com",
            http_client=http,
            max_retries=0,
        )
        instrument_openai_http(SimpleNamespace(root_async_client=client))
        with (
            patch("lib.config.llm_http_logging.monotonic", return_value=10),
            patch("lib.config.llm_diagnostics.monotonic", return_value=250),
        ):
            with pytest.raises(openai.APITimeoutError) as caught:
                await client.responses.create(model="test", input="private")
            details = capture_http_error(caught.value)
        assert details["client_request_id"]
        assert details["attempt_elapsed_ms"] == 240000
        assert details["attempt"] == 1
        assert "status_code" not in details
