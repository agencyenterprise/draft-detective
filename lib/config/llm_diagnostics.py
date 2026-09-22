"""Allowlisted HTTP diagnostics shared by logs and persisted workflow errors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import openai

MAX_DIAGNOSTIC_CHARS = 2_000

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


def capture_http_error(exc: BaseException) -> dict | None:
    """Read public OpenAI SDK fields (also preserved by LangChain errors).

    Capture only the final failed attempt. Connection errors have no response
    or request duration; the logging callback measures the overall call instead.
    """
    if not isinstance(exc, openai.APIError):
        return None
    result: dict[str, Any] = {"endpoint": safe_endpoint(exc.request.url)}
    for name in ("code", "type", "param"):
        value = _scalar(getattr(exc, name))
        if value is not None:
            result[name] = value
    fields = _error_fields(exc.body)
    if fields:
        result["response_error"] = fields
    if isinstance(exc, openai.APIStatusError):
        result["status_code"] = exc.status_code
        if exc.request_id:
            result["request_id"] = _scalar(exc.request_id)
        headers = {
            key: value
            for key in RESPONSE_HEADERS
            if (value := _scalar(exc.response.headers.get(key))) is not None
        }
        if headers:
            result["response_headers"] = headers
        try:
            result["response_elapsed_ms"] = round(
                exc.response.elapsed.total_seconds() * 1000
            )
        except RuntimeError:
            # Synthetic or unclosed responses may not have elapsed timing.
            pass
    return result
