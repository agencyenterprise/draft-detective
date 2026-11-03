"""Tests for how reference validation reports references that failed.

A failed reference costs one entry, not the run, so it is reported as a
warning while other references were validated. When none were, an empty result
would read as an all-clear, so the failures escalate to errors.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lib.workflows.models import ErrorDetails, WorkflowErrorSeverity, WorkflowRunType
from lib.workflows.reference_validation_v2.nodes import reference_validation
from lib.workflows.reference_validation_v2.state import (
    ReferenceValidationV2Item,
    ReferenceValidationV2State,
    ReferenceValidationV2Status,
    ReferenceValidationV2WorkflowConfig,
)

RUN_ID = "4b0f6f3e-0c1d-4a55-9a43-3f1f0b3c2d10"
REFERENCE = "Smith, J. (2020). A study of things. Journal of Studies, 12(3), 45-67."


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(context=SimpleNamespace(workflow_run_id=RUN_ID))


def _item(
    reference_id: str, status: ReferenceValidationV2Status, error: str | None = None
) -> ReferenceValidationV2Item:
    return ReferenceValidationV2Item(
        reference_id=reference_id,
        input_reference=REFERENCE,
        status=status,
        error=error,
        error_details=ErrorDetails(error_type="TimeoutError") if error else None,
    )


def _state(*items: ReferenceValidationV2Item) -> ReferenceValidationV2State:
    return ReferenceValidationV2State(
        type=WorkflowRunType.REFERENCE_VALIDATION_V2,
        config=ReferenceValidationV2WorkflowConfig(
            type=WorkflowRunType.REFERENCE_VALIDATION_V2, project_id="project-1"
        ),
        reference_validations=list(items),
    )


async def _finalize(state: ReferenceValidationV2State) -> dict:
    # Call the node body directly: the register_node wrapper only adds progress
    # tracking, which needs a database.
    return await reference_validation.finalize_validations.__wrapped__(
        state, _runtime()
    )


@pytest.mark.asyncio
async def test_failed_reference_keeps_its_error_details():
    agent = SimpleNamespace(ainvoke=AsyncMock(side_effect=TimeoutError("timed out")))
    with patch.object(
        reference_validation, "ReferenceValidatorV2Agent", return_value=agent
    ):
        result = await reference_validation.validate_single_reference.__wrapped__(
            {"reference_id": "ref-1", "input_reference": REFERENCE},
            SimpleNamespace(context=SimpleNamespace()),
        )

    item = result["reference_validations"][0]
    assert item.status == ReferenceValidationV2Status.ERROR
    assert item.error == "timed out"
    assert item.error_details is not None
    assert item.error_details.error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_every_reference_failing_is_a_blocking_error():
    """With nothing validated, a clean run would read as an all-clear."""
    result = await _finalize(
        _state(
            _item("ref-1", ReferenceValidationV2Status.ERROR, "timed out"),
            _item("ref-2", ReferenceValidationV2Status.ERROR, "timed out"),
        )
    )

    errors = result["errors"]
    assert [e.severity for e in errors] == [
        WorkflowErrorSeverity.ERROR,
        WorkflowErrorSeverity.ERROR,
    ]
    assert errors[0].task_name == "validate_single_reference"
    assert errors[0].workflow_run_id == RUN_ID
    assert errors[0].details is not None
    assert errors[0].details.error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_failed_reference_is_a_warning_while_others_were_validated():
    result = await _finalize(
        _state(
            _item("ref-1", ReferenceValidationV2Status.COMPLETED),
            _item("ref-2", ReferenceValidationV2Status.ERROR, "timed out"),
        )
    )

    assert [e.severity for e in result["errors"]] == [WorkflowErrorSeverity.WARNING]


@pytest.mark.asyncio
async def test_failed_reference_message_names_the_reference_and_the_cause():
    result = await _finalize(
        _state(_item("ref-2", ReferenceValidationV2Status.ERROR, "timed out"))
    )

    message = result["errors"][0].error
    assert "Smith, J. (2020)" in message
    assert "missing from these results" in message
    assert "timed out" in message


@pytest.mark.asyncio
async def test_completed_and_cancelled_references_report_no_errors():
    result = await _finalize(
        _state(
            _item("ref-1", ReferenceValidationV2Status.COMPLETED),
            _item("ref-2", ReferenceValidationV2Status.CANCELLED),
        )
    )

    assert result["errors"] == []
