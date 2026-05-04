"""Unit tests for fail_workflow_run — sets FAILED with metadata and cascade-cancels dependents."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs import fail_workflow_run


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
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch(
            "lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()
        ) as mock_update,
        patch("lib.workflows.dependency_resolver.get_required_dependents", return_value=[]),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=None),
        ),
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
    )


@pytest.mark.asyncio
async def test_fail_calls_cancel_workflow_progress():
    """Progress entries for the failed run are cleaned up like cancellation."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch(
            "lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()
        ) as mock_cancel_progress,
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.dependency_resolver.get_required_dependents", return_value=[]),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=None),
        ),
    ):
        await fail_workflow_run(
            str(run.id),
            "project-1",
            failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
        )

    mock_cancel_progress.assert_awaited_once_with(run.project_id, run.type)


@pytest.mark.asyncio
async def test_fail_cascades_to_pending_dependent_as_cancelled():
    """A failed parent cascade-cancels active dependents (CANCELLED, not FAILED)."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    dependent_run = _make_run(WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.PENDING)

    runs_by_id = {str(run.id): run, str(dependent_run.id): dependent_run}

    def dependents_for(workflow_type):
        return (
            [WorkflowRunType.REFERENCE_EXTRACTION]
            if workflow_type == WorkflowRunType.DOCUMENT_PROCESSING
            else []
        )

    with (
        patch(
            "lib.services.workflow_runs.get_workflow_run",
            new=AsyncMock(side_effect=lambda rid, **kw: runs_by_id[str(rid)]),
        ),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch(
            "lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()
        ) as mock_update,
        patch(
            "lib.workflows.dependency_resolver.get_required_dependents",
            side_effect=dependents_for,
        ),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=dependent_run),
        ),
    ):
        await fail_workflow_run(
            str(run.id),
            "project-1",
            failure_reason=WorkflowRunFailureReason.NO_HEARTBEAT,
        )

    # Dependent must be moved to CANCELLED (cascade semantics), not FAILED.
    dependent_calls = [
        call for call in mock_update.await_args_list if call.args[0] == str(dependent_run.id)
    ]
    assert len(dependent_calls) == 1
    assert dependent_calls[0].args[1] == WorkflowRunStatus.CANCELLED


@pytest.mark.asyncio
async def test_fail_does_not_cascade_to_completed_dependent():
    """A COMPLETED dependent is left untouched when the parent fails."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    dependent_run = _make_run(WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.COMPLETED)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch(
            "lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()
        ) as mock_update,
        patch(
            "lib.workflows.dependency_resolver.get_required_dependents",
            return_value=[WorkflowRunType.REFERENCE_EXTRACTION],
        ),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=dependent_run),
        ),
    ):
        await fail_workflow_run(
            str(run.id),
            "project-1",
            failure_reason=WorkflowRunFailureReason.TIMEOUT,
        )

    cascaded_ids = {call.args[0] for call in mock_update.await_args_list}
    assert str(dependent_run.id) not in cascaded_ids


@pytest.mark.asyncio
async def test_fail_raises_when_run_has_no_project_id():
    """fail_workflow_run requires project_id on the row."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    run.project_id = None

    with patch(
        "lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)
    ):
        with pytest.raises(ValueError, match="no project_id"):
            await fail_workflow_run(
                str(run.id),
                "project-1",
                failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
            )
