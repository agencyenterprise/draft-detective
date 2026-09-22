"""Allowlisted HTTP diagnostics shared by logs and persisted workflow errors."""

from __future__ import annotations

from collections.abc import Mapping
from time import monotonic
from typing import Any
from urllib.parse import urlsplit, urlunsplit

MAX_DIAGNOSTIC_CHARS = 2_000
ATTEMPT_START = "llm_attempt_started"
ATTEMPT_DIAGNOSTICS = "llm_attempt_diagnostics"

RESPONSE_HEADERS = (
    "x-request-id",
    "request-id",
    "apim-request-id",
    "x-ms-request-id",
    "x-ms-correlation-request-id",
    "x-ms-error-code",
    "retry-after",
    "retry-after-ms",
    "openai-processing-ms",
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
)


def safe_endpoint(value: Any) -> str | None:
    """Do not retain credentials, query parameters, or fragments in URLs."""
    if not value:
        return None
    try:
        url = urlsplit(str(value))
        return urlunsplit((url.scheme, url.netloc.rsplit("@", 1)[-1], url.path, "", ""))
    except ValueError:
        return None


def _scalar(value: Any) -> str | int | float | bool | None:
    if isinstance(value, str):
        value = " ".join(value.split())
        if len(value) > MAX_DIAGNOSTIC_CHARS:
            return value[:MAX_DIAGNOSTIC_CHARS] + "... [truncated]"
        return value
    if isinstance(value, (int, float, bool)):
        return value
    return None


def _error_fields(body: Any) -> dict:
    """SDK bodies may contain the envelope or just its inner error object.

    Never copy arbitrary response bodies: gateways can return HTML and error
    payloads can contain request data. Keep only known diagnostic fields.
    """
    if not isinstance(body, Mapping):
        return {}
    fields: dict[str, Any] = {}
    for key in ("code", "type", "param", "message", "activityId", "statusCode"):
        value = _scalar(body.get(key))
        if value is not None:
            fields[key] = value
    for key in ("error", "innererror", "inner_error"):
        nested = body.get(key)
        if isinstance(nested, Mapping):
            # Only one nested level: bound size and handle malformed/cyclic bodies.
            inner = {
                name: value
                for name in ("code", "type", "param", "message", "activityId")
                if (value := _scalar(nested.get(name))) is not None
            }
            if inner:
                fields[key] = inner
    return fields


def request_diagnostics(request: Any) -> dict:
    if request is None:
        return {}
    result: dict[str, Any] = {}
    endpoint = safe_endpoint(getattr(request, "url", None))
    if endpoint:
        result["endpoint"] = endpoint
    headers = getattr(request, "headers", {})
    client_id = _scalar(headers.get("x-client-request-id"))
    if client_id:
        result["client_request_id"] = client_id
    retry_count = headers.get("x-stainless-retry-count", "")
    if str(retry_count).isdigit():
        result["attempt"] = int(retry_count) + 1
    return result


def response_diagnostics(response: Any, body: Any = None) -> dict:
    if response is None:
        return {}
    try:
        request = response.request
    except (AttributeError, RuntimeError):
        request = None
    result = request_diagnostics(request)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        result["status_code"] = status
    headers = getattr(response, "headers", {})
    selected = {
        key: value
        for key in RESPONSE_HEADERS
        if (value := _scalar(headers.get(key))) is not None
    }
    if selected:
        result["response_headers"] = selected
    if body is None:
        try:
            body = response.json()
        except Exception:
            # Empty, HTML, or unread streaming response; never consume it here.
            pass
    fields = _error_fields(body)
    if fields:
        result["response_error"] = fields
    result.update(getattr(response, "extensions", {}).get(ATTEMPT_DIAGNOSTICS, {}))
    return result


def capture_http_error(exc: BaseException) -> dict | None:
    """Follow wrappers (including LangChain's) without losing SDK metadata."""
    seen: set[int] = set()
    current: BaseException | None = exc
    result: dict[str, Any] = {}
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        details = response_diagnostics(response, getattr(current, "body", None))
        for name in ("status_code", "request_id", "code", "type", "param"):
            value = _scalar(getattr(current, name, None))
            if value is not None:
                details[name] = value
        request = getattr(current, "request", None)
        if response is None and request is not None:
            details.update(request_diagnostics(request))
            started = getattr(request, "extensions", {}).get(ATTEMPT_START)
            if isinstance(started, (int, float)):
                details["attempt_elapsed_ms"] = round((monotonic() - started) * 1000)
        for key, value in details.items():
            result.setdefault(key, value)
        current = current.__cause__ or current.__context__
    return result or None
