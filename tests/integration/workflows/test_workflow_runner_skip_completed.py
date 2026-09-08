"""Tests for workflow runner skipping completed workflows."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_runner import start_multiple_workflow_runs
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.registry import get_config_type


@pytest.fixture
def test_context():
    """Common test data used across all tests."""
    project_id = uuid4()
    return {
        "project_id": project_id,
        "user": User(id=uuid4(), email="test@example.com", name="Test User"),
        "workflow_type": WorkflowRunType.REFERENCE_VALIDATION_V2,
    }


def create_run(
    project_id,
    workflow_type: WorkflowRunType,
    status: WorkflowRunStatus = WorkflowRunStatus.COMPLETED,
) -> WorkflowRun:
    """Create a workflow run with the given status for testing."""
    return WorkflowRun(
        id=uuid4(),
        project_id=project_id,
        type=workflow_type,
        status=status,
        langgraph_thread_id=str(uuid4()),
    )


def create_mock_config(project_id: str, workflow_type: WorkflowRunType):
    """Create a minimal valid config for the given workflow type."""
    config_type = get_config_type(workflow_type)
    return config_type(project_id=project_id)


async def run_workflow_with_mocks(
    test_context, completed_workflows, existing_runs=None
):
    """
    Execute workflow runner with mocked dependencies.

    Args:
        test_context: Fixture with project_id, user, workflow_type
        completed_workflows: List of WorkflowRunType that should return as completed
        existing_runs: Optional dict of {WorkflowRunType: WorkflowRunStatus} for
            workflows that already exist in a non-completed state (e.g. CANCELLED).
            Lets tests model dependencies that need to be re-run.

    Returns:
        Tuple of (mock_create, mock_create_config) for assertions
    """
    project_id_str = str(test_context["project_id"])
    request = StartMultipleWorkflowsRequest(
        project_id=project_id_str,
        workflow_types=[test_context["workflow_type"]],
        openai_api_key="test-api-key",
    )

    runs = {
        wf_type: create_run(test_context["project_id"], wf_type)
        for wf_type in completed_workflows
    }
    for wf_type, status in (existing_runs or {}).items():
        runs[wf_type] = create_run(test_context["project_id"], wf_type, status)

    async def mock_get_run(proj_id, workflow_type, **kwargs):
        return runs.get(workflow_type, None)

    def mock_config_factory(project, workflow_type, openai_api_key=None):
        return create_mock_config(project_id_str, workflow_type)

    # Create a mock project object
    mock_project = MagicMock()
    mock_project.id = test_context["project_id"]
    mock_project.current_revision = 1

    with (
        patch(
            "lib.api.services.workflow_runner.get_project_access",
            new=AsyncMock(return_value=(mock_project, AccessLevel.WRITE)),
        ),
        patch(
            "lib.api.services.workflow_runner.assert_project_has_main_file",
            new=AsyncMock(),
        ),
        patch(
            "lib.api.services.workflow_runner.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch(
            "lib.api.services.workflow_runner.create_workflow_run",
            new=AsyncMock(side_effect=lambda **kwargs: str(uuid4())),
        ) as mock_create,
        patch(
            "lib.api.services.workflow_runner.create_workflow_config",
            side_effect=mock_config_factory,
        ) as mock_create_config,
        patch(
            "lib.api.services.workflow_runner.get_approved_gates",
            new=AsyncMock(return_value=set()),
        ),
    ):

        await start_multiple_workflow_runs(
            workflow_types=[test_context["workflow_type"]],
            request=request,
            user=test_context["user"],
            background_tasks=BackgroundTasks(),
        )

        return mock_create, mock_create_config


@pytest.mark.asyncio
async def test_skip_completed_dependencies(test_context):
    """Test that completed dependency workflows are not re-run (unless always_run=True)."""
    # Both dependencies completed → DOCUMENT_PROCESSING still runs (always_run=True)
    # REFERENCE_EXTRACTION is skipped, REFERENCE_VALIDATION runs
    mock_create, _ = await run_workflow_with_mocks(
        test_context,
        [WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunType.REFERENCE_EXTRACTION],
    )

    # 2 workflows: DOCUMENT_PROCESSING (always_run=True) + REFERENCE_VALIDATION
    assert mock_create.call_count == 2
    started_types = {call.kwargs["type"] for call in mock_create.call_args_list}
    assert started_types == {
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_VALIDATION_V2,
    }


@pytest.mark.asyncio
async def test_start_all_when_none_completed(test_context):
    """Test that all workflows start when none are completed."""
    # No workflows completed → start all 3 (including dependencies)
    mock_create, _ = await run_workflow_with_mocks(test_context, [])

    assert mock_create.call_count == 3
    started_types = {call.kwargs["type"] for call in mock_create.call_args_list}
    assert started_types == {
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.REFERENCE_VALIDATION_V2,
    }


@pytest.mark.asyncio
async def test_partial_completion(test_context):
    """Test that only incomplete workflows are started (unless always_run=True)."""
    # Only DOCUMENT_PROCESSING completed → but it has always_run=True, so still runs
    # REFERENCE_EXTRACTION and REFERENCE_VALIDATION also run
    mock_create, _ = await run_workflow_with_mocks(
        test_context, [WorkflowRunType.DOCUMENT_PROCESSING]
    )

    # 3 workflows: DOCUMENT_PROCESSING (always_run=True) + REFERENCE_EXTRACTION + REFERENCE_VALIDATION
    assert mock_create.call_count == 3
    started_types = {call.kwargs["type"] for call in mock_create.call_args_list}
    assert WorkflowRunType.DOCUMENT_PROCESSING in started_types  # always_run=True
    assert WorkflowRunType.REFERENCE_EXTRACTION in started_types
    assert WorkflowRunType.REFERENCE_VALIDATION_V2 in started_types


@pytest.mark.asyncio
async def test_requested_workflow_is_started_even_if_completed(test_context):
    """Test that requested workflows are started even if completed, and always_run dependencies still run."""
    # All workflows completed → DOCUMENT_PROCESSING still runs (always_run=True)
    # REFERENCE_EXTRACTION is skipped, REFERENCE_VALIDATION runs (explicitly requested)
    mock_create, mock_create_config = await run_workflow_with_mocks(
        test_context,
        [
            WorkflowRunType.DOCUMENT_PROCESSING,
            WorkflowRunType.REFERENCE_EXTRACTION,
            WorkflowRunType.REFERENCE_VALIDATION_V2,
        ],
    )

    # 2 workflows: DOCUMENT_PROCESSING (always_run=True) + REFERENCE_VALIDATION (requested)
    assert mock_create.call_count == 2
    started_types = {call.kwargs["type"] for call in mock_create.call_args_list}
    assert started_types == {
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_VALIDATION_V2,
    }
    assert mock_create_config.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extraction_status",
    [WorkflowRunStatus.CANCELLED, WorkflowRunStatus.FAILED],
)
async def test_rerun_extraction_when_dependency_cancelled_or_failed(
    test_context, extraction_status
):
    """A cancelled/failed reference extraction dependency must be re-run.

    Regression test: previously REFERENCE_EXTRACTION was skipped on any
    existing run regardless of status, so a cancelled extraction left
    REFERENCE_VALIDATION stuck (it would self-cancel waiting on a dead
    dependency). It must now be re-created so dependents can proceed.
    """
    mock_create, _ = await run_workflow_with_mocks(
        test_context,
        [WorkflowRunType.DOCUMENT_PROCESSING],
        existing_runs={WorkflowRunType.REFERENCE_EXTRACTION: extraction_status},
    )

    started_types = {call.kwargs["type"] for call in mock_create.call_args_list}
    assert WorkflowRunType.REFERENCE_EXTRACTION in started_types
    assert WorkflowRunType.REFERENCE_VALIDATION_V2 in started_types


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extraction_status",
    [WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING],
)
async def test_skip_extraction_when_already_in_flight(test_context, extraction_status):
    """An in-flight reference extraction must not be duplicated.

    Reference extraction runs only once per project. When it's already
    PENDING/RUNNING, starting a dependent should NOT create a second
    extraction run — the dependent waits on the existing one.
    """
    mock_create, _ = await run_workflow_with_mocks(
        test_context,
        [WorkflowRunType.DOCUMENT_PROCESSING],
        existing_runs={WorkflowRunType.REFERENCE_EXTRACTION: extraction_status},
    )

    started_types = {call.kwargs["type"] for call in mock_create.call_args_list}
    assert WorkflowRunType.REFERENCE_EXTRACTION not in started_types
    assert WorkflowRunType.REFERENCE_VALIDATION_V2 in started_types
