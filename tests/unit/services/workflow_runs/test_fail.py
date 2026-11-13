"""Unit tests for fail_workflow_run: sets FAILED with its metadata. Cancelling
dependents is the promoter's job (see test_promotion_plan.py)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs.service import fail_workflow_run


def _make_run(
    run_type: WorkflowRunType,
    status: WorkflowRunStatus,
    run_id: str | None = None,
    project_id: str = "project-1",
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id or str(uuid.uuid4()),
        project_id=project_id,
        type=run_type,
        status=status,
        langgraph_thread_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_fail_marks_run_failed_with_reason_and_message():
    """The target run is updated to FAILED with the provided reason and message."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run",
            new=AsyncMock(return_value=run),
        ),
        patch(
            "lib.services.workflow_runs.service.cancel_workflow_progress",
            new=AsyncMock(),
        ),
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_status",
            new=AsyncMock(),
        ) as mock_update,
    ):
        await fail_workflow_run(
            str(run.id),
            "project-1",
            failure_reason=WorkflowRunFailureReason.TIMEOUT,
            failure_message="exceeded max_duration",
        )

    mock_update.assert_any_await(
        str(run.id),
        WorkflowRunStatus.FAILED,
        failure_reason=WorkflowRunFailureReason.TIMEOUT,
        failure_message="exceeded max_duration",
        clean_up_state=None,
    )


@pytest.mark.asyncio
async def test_fail_calls_cancel_workflow_progress():
    """Progress entries for the failed run are cleaned up like cancellation."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)

    with (
        patch(
            "lib.services.workflow_runs.service.get_workflow_run",
            new=AsyncMock(return_value=run),
        ),
        patch(
            "lib.services.workflow_runs.service.cancel_workflow_progress",
            new=AsyncMock(),
        ) as mock_cancel_progress,
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_status",
            new=AsyncMock(),
        ),
    ):
        await fail_workflow_run(
            str(run.id),
            "project-1",
            failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
        )

    mock_cancel_progress.assert_awaited_once_with(
        run.project_id, run.type, only_run_id=None
    )


@pytest.mark.asyncio
async def test_fail_raises_when_run_has_no_project_id():
    """fail_workflow_run requires project_id on the row."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    run.project_id = None

    with patch(
        "lib.services.workflow_runs.service.get_workflow_run",
        new=AsyncMock(return_value=run),
    ):
        with pytest.raises(ValueError, match="no project_id"):
            await fail_workflow_run(
                str(run.id),
                "project-1",
                failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
            )
