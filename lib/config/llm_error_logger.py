"""Structured logging for LLM (chat + embeddings) errors.

Emits grep-friendly single-line log records when an LLM or embeddings call
fails, including the agent/caller name, model, provider, and — when it can be
discovered from metadata — the API endpoint. Rate-limit (HTTP 429) failures
use a distinct `LLM_RATE_LIMIT` prefix so they can be isolated with a simple
`grep '^LLM_RATE_LIMIT'`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

if TYPE_CHECKING:
    # Imported only for typing to avoid a circular import:
    # lib.workflows.context -> lib.services.vector_store -> lib.config.llm_error_logger.
    # At runtime we duck-type access to context.workflow_run_id / context.project_id.
    from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

_RATE_LIMIT_PREFIX = "LLM_RATE_LIMIT"
_GENERIC_ERROR_PREFIX = "LLM_ERROR"

# Attribute names used by common LangChain chat/embeddings classes to hold
# the provider base URL. Checked in order; the first non-empty value wins.
_ENDPOINT_ATTRS = ("openai_api_base", "anthropic_api_url", "base_url")

_UNKNOWN = "unknown"


@dataclass(frozen=True)
class _CallMetadata:
    """Metadata captured at LLM call start, consumed at error/end time.

    The callback receives `serialized` + `metadata` + `tags` only on
    `on_chat_model_start` / `on_llm_start` — not on `on_llm_error` — so we
    cache what we need keyed by the call's `run_id`.
    """

    agent_name: str
    model_name: str
    provider: str
    endpoint: Optional[str]


def _is_rate_limit_error(error: BaseException) -> bool:
    """Return True if the given exception looks like a provider 429.

    Works across OpenAI/Anthropic SDKs (both set `status_code=429` on their
    `RateLimitError` subclasses) and any other httpx-style error that exposes
    a `status_code` attribute.
    """
    return getattr(error, "status_code", None) == 429


def _flatten_message(error: BaseException) -> str:
    """Return a grep-friendly, single-line error message.

    Newlines and double quotes are replaced so the `message="..."` field
    stays parseable by simple `grep`/`awk` pipelines, but the full text is
    preserved.
    """
    return str(error).replace("\n", " ").replace('"', "'").strip()


def _status_code(error: BaseException) -> str:
    code = getattr(error, "status_code", None)
    return str(code) if code is not None else "-"


def _endpoint_from_obj(obj: Any) -> Optional[str]:
    """Try to read a base URL / endpoint string off a chat model or embeddings
    client. Returns None if no known attribute is set."""
    if obj is None:
        return None
    for attr in _ENDPOINT_ATTRS:
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    # Some LangChain wrappers expose the underlying SDK client; check its base_url.
    client = getattr(obj, "client", None) or getattr(obj, "_client", None)
    if client is not None:
        base_url = getattr(client, "base_url", None)
        if base_url:
            return str(base_url)
    return None


def _endpoint_from_error(error: BaseException) -> Optional[str]:
    """Try to read the request URL off an httpx-style error's response."""
    response = getattr(error, "response", None)
    if response is None:
        return None
    request = getattr(response, "request", None)
    if request is None:
        return None
    url = getattr(request, "url", None)
    return str(url) if url else None


def _endpoint_from_serialized(
    serialized: Optional[dict[str, Any]], extra_kwargs: dict[str, Any]
) -> Optional[str]:
    """Pull a base URL out of LangChain's `serialized` dict or the
    `invocation_params` kwarg passed alongside `on_(chat_model|llm)_start`."""
    candidates: list[dict[str, Any]] = []
    if isinstance(serialized, dict):
        inner = serialized.get("kwargs")
        if isinstance(inner, dict):
            candidates.append(inner)
    invocation_params = extra_kwargs.get("invocation_params")
    if isinstance(invocation_params, dict):
        candidates.append(invocation_params)
    for candidate in candidates:
        for attr in _ENDPOINT_ATTRS:
            value = candidate.get(attr)
            if value:
                return str(value)
    return None


def _agent_name_from_metadata(
    metadata: Optional[dict[str, Any]], tags: Optional[list[str]]
) -> str:
    """Derive a meaningful "agent" label for the log line.

    LangGraph injects `langgraph_node` into the runnable metadata, which is
    the most useful identifier from the runner's perspective — it tells the
    operator which workflow stage was running when the call failed. Falls
    back to other hints before giving up.
    """
    if metadata:
        node = metadata.get("langgraph_node")
        if node:
            return str(node)
    if tags:
        for tag in tags:
            if tag.startswith("graph:node:"):
                return tag.removeprefix("graph:node:")
    return _UNKNOWN


def _format_log_line(
    *,
    is_rate_limit: bool,
    caller: str,
    model_name: str,
    provider: str,
    endpoint: Optional[str],
    workflow_run_id: Optional[str],
    project_id: Optional[str],
    status: str,
    error_type: str,
    message: str,
) -> str:
    """Build a single-line `PREFIX key=value …` record.

    Fields with no value are rendered as `-` so the column layout is stable
    (helpful for `awk`). The `endpoint` field is omitted entirely when we
    couldn't discover a value — we prefer omission over guessing.
    """
    prefix = _RATE_LIMIT_PREFIX if is_rate_limit else _GENERIC_ERROR_PREFIX
    parts = [
        prefix,
        f"agent={caller or _UNKNOWN}",
        f"model={model_name or _UNKNOWN}",
        f"provider={provider or '-'}",
    ]
    if endpoint:
        parts.append(f"endpoint={endpoint}")
    parts.extend(
        [
            f"workflow_run_id={workflow_run_id or '-'}",
            f"project_id={project_id or '-'}",
            f"status={status}",
            f"error_type={error_type}",
            f'message="{message}"',
        ]
    )
    return " ".join(parts)


def _emit(line: str, *, is_rate_limit: bool) -> None:
    if is_rate_limit:
        logger.warning(line)
    else:
        logger.error(line)


class ErrorLoggingCallback(BaseCallbackHandler):
    """LangChain callback that logs LLM errors with model/endpoint context.

    Designed to be attached once per workflow run (in `lib/workflows/runner.py`),
    next to the langfuse handler. The callback derives model, provider,
    endpoint, and the workflow stage ("agent") dynamically from each call's
    metadata — it doesn't need per-agent wiring.

    The workflow context (workflow_run_id, project_id) is bound at
    construction time because it's stable for the duration of a single
    workflow execution.
    """

    def __init__(
        self,
        *,
        workflow_run_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        self._workflow_run_id = workflow_run_id
        self._project_id = project_id
        # Per-call metadata captured at start, consumed at error/end.
        # Bounded — entries removed in on_llm_end / on_llm_error.
        self._calls: dict[UUID, _CallMetadata] = {}

    # --- start hooks: capture metadata keyed by run_id -------------------

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: Any,  # list[list[BaseMessage]] — typing loose to avoid import
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._calls[run_id] = self._build_metadata(
            serialized=serialized, tags=tags, metadata=metadata, extra_kwargs=kwargs
        )

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._calls[run_id] = self._build_metadata(
            serialized=serialized, tags=tags, metadata=metadata, extra_kwargs=kwargs
        )

    @staticmethod
    def _build_metadata(
        *,
        serialized: dict[str, Any],
        tags: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
        extra_kwargs: dict[str, Any],
    ) -> _CallMetadata:
        # LangChain populates `metadata["ls_model_name"]` and
        # `metadata["ls_provider"]` for all chat models via LangSmithParams.
        model_name = (metadata or {}).get("ls_model_name") or _UNKNOWN
        provider = (metadata or {}).get("ls_provider") or ""
        endpoint = _endpoint_from_serialized(serialized, extra_kwargs)
        return _CallMetadata(
            agent_name=_agent_name_from_metadata(metadata, tags),
            model_name=str(model_name),
            provider=str(provider),
            endpoint=endpoint,
        )

    # --- end / error hooks: consume cached metadata ----------------------

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        # Successful call — drop the cached metadata to avoid unbounded growth.
        self._calls.pop(run_id, None)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        meta = self._calls.pop(run_id, None)
        is_rate_limit = _is_rate_limit_error(error)
        line = _format_log_line(
            is_rate_limit=is_rate_limit,
            caller=meta.agent_name if meta else _UNKNOWN,
            model_name=meta.model_name if meta else _UNKNOWN,
            provider=meta.provider if meta else "",
            endpoint=(meta.endpoint if meta else None) or _endpoint_from_error(error),
            workflow_run_id=self._workflow_run_id,
            project_id=self._project_id,
            status=_status_code(error),
            error_type=type(error).__name__,
            message=_flatten_message(error),
        )
        _emit(line, is_rate_limit=is_rate_limit)


def log_embedding_error(
    error: BaseException,
    *,
    caller: str,
    model: str,
    provider: str,
    embeddings_client: Any = None,
    context: Optional[ContextSchema] = None,
) -> None:
    """Log an error from an embeddings call in the same format as chat errors.

    Unlike chat models, embeddings calls in this codebase don't run through a
    LangChain callback (they're invoked directly from `vector_store.py` and
    `reference_embedding_matcher.py`). This helper is called from the
    `except` block of those call sites.
    """
    is_rate_limit = _is_rate_limit_error(error)
    endpoint = _endpoint_from_obj(embeddings_client) or _endpoint_from_error(error)
    line = _format_log_line(
        is_rate_limit=is_rate_limit,
        caller=caller,
        model_name=model,
        provider=provider,
        endpoint=endpoint,
        workflow_run_id=(
            str(context.workflow_run_id)
            if context is not None and getattr(context, "workflow_run_id", None)
            else None
        ),
        project_id=(
            str(context.project_id)
            if context is not None and getattr(context, "project_id", None)
            else None
        ),
        status=_status_code(error),
        error_type=type(error).__name__,
        message=_flatten_message(error),
    )
    _emit(line, is_rate_limit=is_rate_limit)
