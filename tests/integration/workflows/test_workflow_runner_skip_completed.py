"""Tests for workflow runner skipping completed workflows."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import BackgroundTasks

from api.services.workflow_runner import start_multiple_workflow_runs
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig


@pytest.fixture
def test_context():
    """Common test data used across all tests."""
    return {
        "project_id": str(uuid4()),
        "user": User(id=str(uuid4()), email="test@example.com"),
        "workflow_type": WorkflowRunType.REFERENCE_VALIDATION,
    }


def create_completed_run(
    project_id: str, workflow_type: WorkflowRunType
) -> WorkflowRun:
    """Create a completed workflow run for testing."""
    return WorkflowRun(
        id=str(uuid4()),
        project_id=project_id,
        type=workflow_type,
        status=WorkflowRunStatus.COMPLETED,
        langgraph_thread_id=str(uuid4()),
    )


async def run_workflow_with_mocks(test_context, completed_workflows):
    """
    Execute workflow runner with mocked dependencies.

    Args:
        test_context: Fixture with project_id, user, workflow_type
        completed_workflows: List of WorkflowRunType that should return as completed

    Returns:
        Tuple of (mock_upsert, mock_create_config) for assertions
    """
    config = SubstantiationWorkflowConfig(
        project_id=test_context["project_id"],
        workflow_types=[test_context["workflow_type"]],
    )

    completed_runs = {
        wf_type: create_completed_run(test_context["project_id"], wf_type)
        for wf_type in completed_workflows
    }

    async def mock_get_run(proj_id, workflow_type):
        return completed_runs.get(workflow_type, None)

    with (
        patch(
            "api.services.workflow_runner.get_user_project_detailed", new=AsyncMock()
        ),
        patch(
            "api.services.workflow_runner.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch(
            "api.services.workflow_runner.upsert_workflow_run", new=AsyncMock()
        ) as mock_upsert,
        patch(
            "api.services.workflow_runner.create_workflow_config"
        ) as mock_create_config,
    ):

        await start_multiple_workflow_runs(
            workflow_types=[test_context["workflow_type"]],
            base_config=config,
            user=test_context["user"],
            background_tasks=BackgroundTasks(),
        )

        return mock_upsert, mock_create_config


@pytest.mark.asyncio
async def test_skip_completed_dependencies(test_context):
    """Test that completed dependency workflows are not re-run."""
    # Both dependencies completed → only start REFERENCE_VALIDATION
    mock_upsert, _ = await run_workflow_with_mocks(
        test_context,
        [WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunType.CLAIM_SUBSTANTIATION],
    )

    assert mock_upsert.call_count == 1
    assert mock_upsert.call_args.kwargs["type"] == WorkflowRunType.REFERENCE_VALIDATION


@pytest.mark.asyncio
async def test_start_all_when_none_completed(test_context):
    """Test that all workflows start when none are completed."""
    # No workflows completed → start all 3 (including dependencies)
    mock_upsert, _ = await run_workflow_with_mocks(test_context, [])

    assert mock_upsert.call_count == 3
    started_types = {call.kwargs["type"] for call in mock_upsert.call_args_list}
    assert started_types == {
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.CLAIM_SUBSTANTIATION,
        WorkflowRunType.REFERENCE_VALIDATION,
    }


@pytest.mark.asyncio
async def test_partial_completion(test_context):
    """Test that only incomplete workflows are started."""
    # Only DOCUMENT_PROCESSING completed → start other 2
    mock_upsert, _ = await run_workflow_with_mocks(
        test_context, [WorkflowRunType.DOCUMENT_PROCESSING]
    )

    assert mock_upsert.call_count == 2
    started_types = {call.kwargs["type"] for call in mock_upsert.call_args_list}
    assert WorkflowRunType.DOCUMENT_PROCESSING not in started_types
    assert WorkflowRunType.CLAIM_SUBSTANTIATION in started_types
    assert WorkflowRunType.REFERENCE_VALIDATION in started_types


@pytest.mark.asyncio
async def test_skip_all_when_all_completed(test_context):
    """Test that no workflows start when all are completed."""
    # All workflows completed → start nothing
    mock_upsert, mock_create_config = await run_workflow_with_mocks(
        test_context,
        [
            WorkflowRunType.DOCUMENT_PROCESSING,
            WorkflowRunType.CLAIM_SUBSTANTIATION,
            WorkflowRunType.REFERENCE_VALIDATION,
        ],
    )

    assert mock_upsert.call_count == 0
    assert mock_create_config.call_count == 0
