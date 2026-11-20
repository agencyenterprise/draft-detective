"""Tests for the diagnostics captured alongside persisted workflow errors.

Covers the failure that motivated this module: a structured-output parse error
whose only surviving record used to be `str(exc)`, with the truncated model
output and the finish reason lost to the server log.
"""

from __future__ import annotations

import json

from langchain.agents.structured_output import StructuredOutputValidationError
from langchain_core.exceptions import ModelRefusalError
from langchain_core.messages import AIMessage

from lib.workflows.error_details import (
    MAX_RAW_OUTPUT_CHARS,
    MAX_TRACEBACK_CHARS,
    build_workflow_error,
    capture_error_details,
)

TRUNCATED_JSON = '{"issues": [{"quoted_text": "Rapid advancements in AI'


def _structured_output_error(content: str) -> StructuredOutputValidationError:
    """Reproduce LangChain's failure path: json.loads on a truncated response."""
    ai_message = AIMessage(
        content=content,
        response_metadata={
            "model_name": "gpt-5.5",
            "finish_reason": "length",
        },
        usage_metadata={
            "input_tokens": 12_000,
            "output_tokens": 2_048,
            "total_tokens": 14_048,
        },
    )
    try:
        json.loads(content)
    except json.JSONDecodeError as decode_error:
        try:
            raise ValueError(
                "Native structured output expected valid JSON for "
                f"SectionValidationResult, but parsing failed: {decode_error}."
            ) from decode_error
        except ValueError as source:
            return StructuredOutputValidationError(
                "SectionValidationResult", source, ai_message
            )
    raise AssertionError("content was expected to be invalid JSON")


def _raise_and_capture(exc: BaseException):
    """Capture with a real traceback attached, as a node would."""
    try:
        raise exc
    except BaseException as raised:  # noqa: BLE001 - mirrors the node's catch-all
        return capture_error_details(raised)


def test_captures_raw_model_output_from_structured_output_error():
    details = _raise_and_capture(_structured_output_error(TRUNCATED_JSON))

    assert details.error_type == "StructuredOutputValidationError"
    assert details.raw_model_output == TRUNCATED_JSON


def test_captures_the_response_a_model_refusal_was_raised_over():
    refused = AIMessage(
        content="I can't help with that.",
        response_metadata={"model_name": "gpt-5.5", "finish_reason": "content_filter"},
    )

    details = _raise_and_capture(ModelRefusalError(raw_message=refused))

    assert details.raw_model_output == "I can't help with that."
    assert details.llm_metadata is not None
    assert details.llm_metadata["finish_reason"] == "content_filter"


def test_captures_finish_reason_and_token_usage():
    details = _raise_and_capture(_structured_output_error(TRUNCATED_JSON))

    assert details.llm_metadata is not None
    assert details.llm_metadata["finish_reason"] == "length"
    assert details.llm_metadata["model_name"] == "gpt-5.5"
    assert details.llm_metadata["usage_metadata"]["output_tokens"] == 2_048


def test_traceback_includes_the_chained_cause():
    details = _raise_and_capture(_structured_output_error(TRUNCATED_JSON))

    assert details.traceback is not None
    assert "StructuredOutputValidationError" in details.traceback
    assert "Unterminated string" in details.traceback


def test_captures_content_from_a_bare_json_decode_error():
    """No AIMessage on the exception — fall back to the text json choked on."""
    try:
        json.loads(TRUNCATED_JSON)
    except json.JSONDecodeError as decode_error:
        details = _raise_and_capture(decode_error)

    assert details.error_type == "JSONDecodeError"
    assert details.raw_model_output == TRUNCATED_JSON
    assert details.llm_metadata is None


def test_plain_exception_captures_traceback_only():
    details = _raise_and_capture(RuntimeError("boom"))

    assert details.error_type == "RuntimeError"
    assert details.raw_model_output is None
    assert details.llm_metadata is None
    assert details.traceback is not None
    assert "boom" in details.traceback


def test_oversized_model_output_is_truncated():
    oversized = '{"issues": "' + "x" * (MAX_RAW_OUTPUT_CHARS * 2)
    details = _raise_and_capture(_structured_output_error(oversized))

    assert details.raw_model_output is not None
    assert details.raw_model_output.endswith("[truncated]")
    assert len(details.raw_model_output) < len(oversized)
    assert details.traceback is not None
    assert len(details.traceback) <= MAX_TRACEBACK_CHARS + len("... [truncated]")


def test_build_workflow_error_attaches_details_and_defaults_message():
    error = build_workflow_error(
        task_name="validate_section",
        exc=_structured_output_error(TRUNCATED_JSON),
        workflow_run_id="run-1",
        chunk_index=8,
    )

    assert error.task_name == "validate_section"
    assert error.chunk_index == 8
    assert error.workflow_run_id == "run-1"
    assert "Failed to parse structured output" in error.error
    assert error.details is not None
    assert error.details.raw_model_output == TRUNCATED_JSON


def test_build_workflow_error_honours_a_custom_message():
    error = build_workflow_error(
        task_name="convert_to_markdown",
        exc=RuntimeError("boom"),
        message="Failed to convert main doc.pdf (file_id=abc): boom",
    )

    assert error.error == "Failed to convert main doc.pdf (file_id=abc): boom"
    assert error.details is not None
    assert error.details.error_type == "RuntimeError"


def test_details_survive_a_json_round_trip():
    """state_json is jsonb — the payload has to serialise cleanly."""
    error = build_workflow_error(
        task_name="validate_section",
        exc=_structured_output_error(TRUNCATED_JSON),
    )

    restored = type(error).model_validate(json.loads(error.model_dump_json()))

    assert restored.details is not None
    assert restored.details.raw_model_output == TRUNCATED_JSON
    assert restored.details.llm_metadata == error.details.llm_metadata
