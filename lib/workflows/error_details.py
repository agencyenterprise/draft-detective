"""Capture debuggable diagnostics from caught exceptions.

Workflow nodes swallow exceptions and persist them as `WorkflowError` records in
`workflow_runs.state_json`. Historically only `str(exc)` survived, so diagnosing
a failure meant finding the server log of that run. These helpers attach the
traceback, the raw LLM output, and the failing call's response metadata to the
persisted record instead.
"""

import json
import logging
import traceback
from typing import Any, Optional

from langchain_core.messages import AIMessage

from lib.agents.structured_output_salvage import ai_message_text
from lib.config.llm_diagnostics import capture_http_error
from lib.workflows.models import ErrorDetails, WorkflowError, WorkflowErrorSeverity

logger = logging.getLogger(__name__)

MAX_TRACEBACK_CHARS = 8_000
MAX_RAW_OUTPUT_CHARS = 12_000
MAX_METADATA_VALUE_CHARS = 2_000

_TRUNCATION_SUFFIX = "... [truncated]"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + _TRUNCATION_SUFFIX


def _causes(exc: BaseException) -> list[BaseException]:
    """The exception plus its `__cause__`/`__context__` chain, cycle-safe."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _find_ai_message(exc: BaseException) -> Optional[AIMessage]:
    """Locate the LLM response an exception was raised over.

    LangChain's structured-output errors expose the offending `AIMessage` as an
    `ai_message` attribute. Matched by attribute rather than by exception class
    so this keeps working across LangChain refactors and covers any other
    exception that adopts the same convention.
    """
    for link in _causes(exc):
        candidate = getattr(link, "ai_message", None)
        if isinstance(candidate, AIMessage):
            return candidate
    return None


def _decoded_document(exc: BaseException) -> Optional[str]:
    """The text a `json.JSONDecodeError` in the chain choked on."""
    for link in _causes(exc):
        if isinstance(link, json.JSONDecodeError):
            return link.doc
    return None


def _jsonable(value: Any) -> Any:
    """Coerce arbitrary metadata into something jsonb can store."""
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)


def _llm_metadata(message: AIMessage) -> Optional[dict]:
    """Response metadata for the failing call: model, finish reason, usage.

    `finish_reason` (or the Responses API's `incomplete_details`) is what
    distinguishes a model that emitted malformed output from one that was cut
    off mid-response, so it is worth persisting verbatim.
    """
    metadata: dict[str, Any] = {}

    for key, value in (getattr(message, "response_metadata", None) or {}).items():
        serialized = _jsonable(value)
        if len(json.dumps(serialized, default=str)) <= MAX_METADATA_VALUE_CHARS:
            metadata[key] = serialized

    usage = getattr(message, "usage_metadata", None)
    if usage:
        metadata["usage_metadata"] = _jsonable(usage)

    if message.id:
        metadata.setdefault("message_id", message.id)

    return metadata or None


def capture_error_details(exc: BaseException) -> ErrorDetails:
    """Build the diagnostic payload for a caught exception."""
    ai_message = _find_ai_message(exc)

    raw_output: Optional[str] = None
    if ai_message is not None:
        raw_output = ai_message_text(ai_message) or None
    if raw_output is None:
        raw_output = _decoded_document(exc)

    metadata = _llm_metadata(ai_message) if ai_message is not None else None
    http_error = capture_http_error(exc)
    if http_error:
        metadata = {**(metadata or {}), "http_error": http_error}

    return ErrorDetails(
        error_type=type(exc).__name__,
        traceback=_truncate(
            "".join(traceback.format_exception(exc)), MAX_TRACEBACK_CHARS
        ),
        raw_model_output=(
            _truncate(raw_output, MAX_RAW_OUTPUT_CHARS) if raw_output else None
        ),
        llm_metadata=metadata,
    )


def build_workflow_error(
    task_name: str,
    exc: BaseException,
    workflow_run_id: Optional[str] = None,
    chunk_index: Optional[int] = None,
    message: Optional[str] = None,
    severity: WorkflowErrorSeverity = WorkflowErrorSeverity.ERROR,
) -> WorkflowError:
    """Build a `WorkflowError` that carries full diagnostics for `exc`.

    Args:
        task_name: Name of the task or node that failed.
        exc: The caught exception.
        workflow_run_id: Run the failure belongs to.
        chunk_index: Chunk the failure belongs to, when chunk-scoped.
        message: Overrides the human-readable message; defaults to `str(exc)`.
        severity: `WARNING` when the failure was recovered from and the run
            should still count as completed.
    """
    return WorkflowError(
        task_name=task_name,
        error=message if message is not None else str(exc),
        chunk_index=chunk_index,
        workflow_run_id=workflow_run_id,
        severity=severity,
        details=capture_error_details(exc),
    )
