"""HTTP diagnostics stay useful through SDK wrappers without copying secrets."""

import json
from datetime import timedelta
from unittest.mock import patch

import httpx2
import openai
import pytest

from langchain_openai import ChatOpenAI

from lib.config.llm_diagnostics import capture_http_error
from lib.config.llm_error_logger import ErrorLoggingCallback
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


def test_gateway_diagnostics_survive_persistence():
    error = make_error()
    details = capture_http_error(error)
    assert details["status_code"] == 500
    assert details["request_id"] == "req-1"
    assert details["response_headers"]["apim-request-id"] == "apim-1"
    assert details["response_error"]["activityId"] == "activity-1"
    assert details["endpoint"] == "https://gateway.example/responses"
    assert "secret" not in json.dumps(details)
    assert "private document" not in json.dumps(details)
    saved = build_workflow_error("check_abbreviations", error)
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


@pytest.mark.parametrize("body", [None, "<html>private proxy details</html>"])
def test_non_json_error_body_is_not_copied(body):
    error = make_error()
    error.body = body
    details = capture_http_error(error)
    assert details["status_code"] == 500
    assert "response_error" not in details
    assert "response_elapsed_ms" not in details


def test_only_final_sdk_retry_details_are_captured():
    attempts = []

    def handle(request):
        attempts.append(request)
        response = httpx2.Response(
            500,
            headers={"x-request-id": f"req-{len(attempts)}"},
            json={"error": {"code": "server_error", "message": "failed"}},
        )
        response.elapsed = timedelta(seconds=240)
        return response

    with httpx2.Client(transport=httpx2.MockTransport(handle)) as http:
        client = openai.OpenAI(
            api_key="test-key",
            base_url="https://example.com",
            http_client=http,
            max_retries=1,
        )
        with patch("openai._base_client.time.sleep"):
            with pytest.raises(openai.InternalServerError) as caught:
                client.responses.create(model="test", input="private document")
        details = capture_http_error(caught.value)
    assert len(attempts) == 2
    assert details["request_id"] == "req-2"
    assert details["code"] == "server_error"
    assert details["response_elapsed_ms"] == 240000
    assert all("x-client-request-id" not in r.headers for r in attempts)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_responses_api", [False, True])
async def test_langchain_error_reaches_logs_and_saved_details(
    caplog, use_responses_api
):

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
            use_responses_api=use_responses_api,
        )
        callback = ErrorLoggingCallback(
            workflow_run_id="workflow-1", project_id="project-1"
        )
        with pytest.raises(Exception) as caught:
            await model.ainvoke("private document", config={"callbacks": [callback]})
        details = capture_http_error(caught.value)
        assert details["response_headers"]["x-request-id"] == "req-langchain"
        assert details["response_error"]["activityId"] == "gateway-activity"
        assert isinstance(caught.value, openai.APIStatusError)
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
async def test_timeout_captures_endpoint_without_inventing_response_details():
    async def handle(request):
        raise httpx2.ReadTimeout("timed out", request=request)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as http:
        client = openai.AsyncOpenAI(
            api_key="test-key",
            base_url="https://example.com",
            http_client=http,
            max_retries=0,
        )
        with pytest.raises(openai.APITimeoutError) as caught:
            await client.responses.create(model="test", input="private")
        assert capture_http_error(caught.value) == {
            "endpoint": "https://example.com/responses"
        }
