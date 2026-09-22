"""Per-attempt OpenAI HTTP timing, including retries hidden by LangChain.

Hooks are installed once on the existing SDK HTTP clients, preserving their
proxy/TLS/timeout/pooling configuration. They carry no workflow-specific state
because LangChain may share clients between models and concurrent workflows.
"""

import json
import logging
from time import monotonic
from typing import Any
from uuid import uuid4

from lib.config.llm_diagnostics import (
    ATTEMPT_DIAGNOSTICS,
    ATTEMPT_START,
    request_diagnostics,
    response_diagnostics,
)

logger = logging.getLogger(__name__)


def _request(request: Any) -> None:
    try:
        request.extensions[ATTEMPT_START] = monotonic()
        # Available even when a timeout prevents receiving a server request ID.
        request.headers.setdefault("x-client-request-id", str(uuid4()))
        logger.info(
            "LLM_HTTP_ATTEMPT_START %s", json.dumps(request_diagnostics(request))
        )
    except Exception:
        logger.debug("Could not record LLM request diagnostics", exc_info=True)


def _response(response: Any) -> None:
    try:
        started = response.request.extensions.get(ATTEMPT_START)
        if started is not None:
            response.extensions[ATTEMPT_DIAGNOSTICS] = {
                "response_headers_elapsed_ms": round((monotonic() - started) * 1000)
            }
        # HTTP hooks run before the response body is read. Do not eagerly read
        # it, especially for streaming calls. The final exception captures the
        # parsed error body later; every attempt still retains response IDs.
        details = response_diagnostics(response, body={})
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(level, "LLM_HTTP_ATTEMPT %s", json.dumps(details))
    except Exception:
        logger.debug("Could not record LLM response diagnostics", exc_info=True)


async def _async_request(request: Any) -> None:
    _request(request)


async def _async_response(response: Any) -> None:
    _response(response)


def instrument_openai_http(model: Any) -> None:
    """Attach stateless hooks to a LangChain OpenAI model's SDK clients."""
    for name, on_request, on_response in (
        ("root_client", _request, _response),
        ("root_async_client", _async_request, _async_response),
    ):
        sdk_client = getattr(model, name, None)
        http_client = getattr(sdk_client, "_client", None)
        if http_client is None:
            continue
        hooks = http_client.event_hooks
        if on_request not in hooks["request"]:
            hooks["request"].append(on_request)
        if on_response not in hooks["response"]:
            hooks["response"].append(on_response)
