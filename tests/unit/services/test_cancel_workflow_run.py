"""Unit tests for cancel_workflow_run cascade logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs import cancel_workflow_run


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


def _patches(
    run: WorkflowRun,
    dependents: list[WorkflowRunType],
    dependent_runs: dict[WorkflowRunType, WorkflowRun | None],
):
    """Return a context-manager stack that mocks all DB calls in cancel_workflow_run."""
    return (
        patch(
            "lib.services.workflow_runs.get_workflow_run",
            new=AsyncMock(return_value=run),
        ),
        patch(
            "lib.services.workflow_progress.cancel_workflow_progress",
            new=AsyncMock(),
        ),
        patch(
            "lib.services.workflow_runs.update_workflow_run_status",
            new=AsyncMock(),
        ),
        patch(
            "lib.workflows.dependency_resolver.get_required_dependents",
            return_value=dependents,
        ),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(side_effect=lambda proj_id, wf_type: dependent_runs.get(wf_type)),
        ),
    )


# ---------------------------------------------------------------------------
# Basic cancellation (no cascade)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_marks_run_cancelled():
    """The target run is updated to CANCELLED."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()) as mock_update,
        patch("lib.workflows.dependency_resolver.get_required_dependents", return_value=[]),
        patch("lib.services.workflow_runs.get_project_workflow_run_by_type", new=AsyncMock(return_value=None)),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    mock_update.assert_any_await(str(run.id), WorkflowRunStatus.CANCELLED)


@pytest.mark.asyncio
async def test_cancel_calls_cancel_workflow_progress():
    """Progress entries for the target run are cleaned up."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()) as mock_cancel_progress,
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()),
        patch("lib.workflows.dependency_resolver.get_required_dependents", return_value=[]),
        patch("lib.services.workflow_runs.get_project_workflow_run_by_type", new=AsyncMock(return_value=None)),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    mock_cancel_progress.assert_awaited_once_with(run.id)


# ---------------------------------------------------------------------------
# Cascade behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_cascades_to_pending_dependent():
    """A PENDING dependent that requires the cancelled run is also cancelled."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    dependent_run = _make_run(WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.PENDING)

    runs_by_id = {str(run.id): run, str(dependent_run.id): dependent_run}

    def dependents_for(workflow_type):
        return [WorkflowRunType.REFERENCE_EXTRACTION] if workflow_type == WorkflowRunType.DOCUMENT_PROCESSING else []

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(side_effect=lambda rid, **kw: runs_by_id[str(rid)])),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()) as mock_update,
        patch("lib.workflows.dependency_resolver.get_required_dependents", side_effect=dependents_for),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=dependent_run),
        ),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    cancelled_ids = {call.args[0] for call in mock_update.await_args_list}
    assert str(dependent_run.id) in cancelled_ids


@pytest.mark.asyncio
async def test_cancel_cascades_to_running_dependent():
    """A RUNNING dependent is also cancelled."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    dependent_run = _make_run(WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.RUNNING)

    runs_by_id = {str(run.id): run, str(dependent_run.id): dependent_run}

    def dependents_for(workflow_type):
        return [WorkflowRunType.REFERENCE_EXTRACTION] if workflow_type == WorkflowRunType.DOCUMENT_PROCESSING else []

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(side_effect=lambda rid, **kw: runs_by_id[str(rid)])),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()) as mock_update,
        patch("lib.workflows.dependency_resolver.get_required_dependents", side_effect=dependents_for),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=dependent_run),
        ),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    cancelled_ids = {call.args[0] for call in mock_update.await_args_list}
    assert str(dependent_run.id) in cancelled_ids


@pytest.mark.asyncio
async def test_cancel_does_not_cascade_to_completed_dependent():
    """A COMPLETED dependent is left untouched."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    dependent_run = _make_run(WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.COMPLETED)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()) as mock_update,
        patch(
            "lib.workflows.dependency_resolver.get_required_dependents",
            return_value=[WorkflowRunType.REFERENCE_EXTRACTION],
        ),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=dependent_run),
        ),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    cancelled_ids = {call.args[0] for call in mock_update.await_args_list}
    assert str(dependent_run.id) not in cancelled_ids


@pytest.mark.asyncio
async def test_cancel_does_not_cascade_to_already_cancelled_dependent():
    """An already-CANCELLED dependent is not cancelled again."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)
    dependent_run = _make_run(WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.CANCELLED)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()) as mock_update,
        patch(
            "lib.workflows.dependency_resolver.get_required_dependents",
            return_value=[WorkflowRunType.REFERENCE_EXTRACTION],
        ),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=dependent_run),
        ),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    # Only the original run should be cancelled
    cancelled_ids = {call.args[0] for call in mock_update.await_args_list}
    assert str(dependent_run.id) not in cancelled_ids


@pytest.mark.asyncio
async def test_cancel_skips_missing_dependent():
    """When no active run exists for a dependent type, cancellation proceeds silently."""
    run = _make_run(WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING)

    with (
        patch("lib.services.workflow_runs.get_workflow_run", new=AsyncMock(return_value=run)),
        patch("lib.services.workflow_progress.cancel_workflow_progress", new=AsyncMock()),
        patch("lib.services.workflow_runs.update_workflow_run_status", new=AsyncMock()) as mock_update,
        patch(
            "lib.workflows.dependency_resolver.get_required_dependents",
            return_value=[WorkflowRunType.REFERENCE_EXTRACTION],
        ),
        patch(
            "lib.services.workflow_runs.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=None),
        ),
    ):
        await cancel_workflow_run(str(run.id), "project-1")

    # Only the original run is updated
    assert mock_update.await_count == 1
    assert mock_update.await_args_list[0].args[0] == str(run.id)
