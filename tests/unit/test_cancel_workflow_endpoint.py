"""Unit tests for the cancel workflow run endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType


def _make_run(status: WorkflowRunStatus, run_id: str | None = None) -> WorkflowRun:
    return WorkflowRun(
        id=run_id or str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        type=WorkflowRunType.DOCUMENT_PROCESSING,
        status=status,
        langgraph_thread_id=str(uuid.uuid4()),
    )


def _mock_user() -> MagicMock:
    user = MagicMock()
    user.id = str(uuid.uuid4())
    return user


@pytest.mark.asyncio
async def test_cancel_completed_workflow_raises_400():
    """Cancelling an already-COMPLETED workflow returns HTTP 400."""
    from lib.api.routers.workflows import cancel_workflow_run_endpoint

    run = _make_run(WorkflowRunStatus.COMPLETED)

    with patch(
        "lib.api.routers.workflows.get_workflow_run",
        new=AsyncMock(return_value=run),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await cancel_workflow_run_endpoint(str(run.id), current_user=_mock_user())

    assert exc_info.value.status_code == 400
    assert "already completed" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_cancel_already_cancelled_workflow_is_idempotent():
    """Cancelling an already-CANCELLED workflow returns 'Already cancelled' without error."""
    from lib.api.routers.workflows import cancel_workflow_run_endpoint

    run = _make_run(WorkflowRunStatus.CANCELLED)

    with patch(
        "lib.api.routers.workflows.get_workflow_run",
        new=AsyncMock(return_value=run),
    ):
        response = await cancel_workflow_run_endpoint(str(run.id), current_user=_mock_user())

    assert response.message == "Already cancelled"
    assert response.workflow_run_id == str(run.id)


@pytest.mark.asyncio
async def test_cancel_running_workflow_triggers_cancellation():
    """Cancelling a RUNNING workflow calls cancel_workflow_run and returns the expected response."""
    from lib.api.routers.workflows import cancel_workflow_run_endpoint

    run = _make_run(WorkflowRunStatus.RUNNING)

    with (
        patch(
            "lib.api.routers.workflows.get_workflow_run",
            new=AsyncMock(return_value=run),
        ),
        patch(
            "lib.api.routers.workflows.cancel_workflow_run",
            new=AsyncMock(),
        ) as mock_cancel,
    ):
        response = await cancel_workflow_run_endpoint(str(run.id), current_user=_mock_user())

    mock_cancel.assert_awaited_once_with(str(run.id), str(run.project_id))
    assert response.message == "Workflow cancellation requested"
    assert response.workflow_run_id == str(run.id)


@pytest.mark.asyncio
async def test_cancel_pending_workflow_triggers_cancellation():
    """Cancelling a PENDING workflow calls cancel_workflow_run and returns the expected response."""
    from lib.api.routers.workflows import cancel_workflow_run_endpoint

    run = _make_run(WorkflowRunStatus.PENDING)

    with (
        patch(
            "lib.api.routers.workflows.get_workflow_run",
            new=AsyncMock(return_value=run),
        ),
        patch(
            "lib.api.routers.workflows.cancel_workflow_run",
            new=AsyncMock(),
        ) as mock_cancel,
    ):
        response = await cancel_workflow_run_endpoint(str(run.id), current_user=_mock_user())

    mock_cancel.assert_awaited_once_with(str(run.id), str(run.project_id))
    assert response.message == "Workflow cancellation requested"
