"""Unit tests for cancel_workflow_run. Cancelling dependents is the promoter's
job (tests/unit/services/workflow_runs/test_promotion_plan.py)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.service import cancel_workflow_run


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


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_marks_run_cancelled():
    """The target run is updated to CANCELLED."""
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
        await cancel_workflow_run(str(run.id), "project-1")

    mock_update.assert_any_await(
        str(run.id),
        WorkflowRunStatus.CANCELLED,
        failure_reason=None,
        failure_message=None,
        clean_up_state=None,
    )


@pytest.mark.asyncio
async def test_cancel_calls_cancel_workflow_progress():
    """Progress entries for the target run are cleaned up."""
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
        await cancel_workflow_run(str(run.id), "project-1")

    mock_cancel_progress.assert_awaited_once_with(
        run.project_id, run.type, only_run_id=None
    )


@pytest.mark.asyncio
async def test_cancelling_one_independent_run_leaves_the_others_progress():
    """Review Assistant requests run side by side, so cancelling one clears only its own progress."""
    run = _make_run(WorkflowRunType.REVIEW_ASSISTANT, WorkflowRunStatus.RUNNING)

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
        await cancel_workflow_run(str(run.id), "project-1")

    mock_cancel_progress.assert_awaited_once_with(
        run.project_id, run.type, only_run_id=run.id
    )
