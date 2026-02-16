"""Tests for workflow orchestration - dependency and same-type locking."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from api.services.workflow_orchestration import wait_for_dependencies
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.models import ClaimExtractionVersion


def create_workflow_run(
    workflow_type: WorkflowRunType,
    status: WorkflowRunStatus,
    run_id: str | None = None,
) -> WorkflowRun:
    """Create a workflow run for testing."""
    return WorkflowRun(
        id=run_id or str(uuid4()),
        project_id=str(uuid4()),
        type=workflow_type,
        status=status,
        langgraph_thread_id=str(uuid4()),
    )


@pytest.fixture
def mock_manifest():
    """Mock workflow manifest with no dependencies."""
    manifest = MagicMock()
    manifest.required_dependencies = []
    manifest.optional_dependencies = []
    return manifest


@pytest.mark.asyncio
async def test_same_type_lock_waits_for_running_workflow(mock_manifest):
    """Test that same-type locking waits for a RUNNING workflow of the same type."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())
    other_run_id = str(uuid4())

    # First call returns RUNNING workflow (different ID), second call returns COMPLETED
    running_run = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.RUNNING,
        run_id=other_run_id,
    )
    completed_run = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.COMPLETED,
        run_id=other_run_id,
    )

    call_count = 0

    async def mock_get_run(proj_id, workflow_type):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return running_run
        return completed_run

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()),
    ):
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    # Should have polled twice (once found RUNNING, once found COMPLETED)
    assert call_count == 2


@pytest.mark.asyncio
async def test_same_type_lock_skips_self(mock_manifest):
    """Test that same-type locking doesn't wait for its own workflow run."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())

    # Return a RUNNING workflow with the SAME ID as current
    own_run = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.RUNNING,
        run_id=current_run_id,
    )

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            return_value=own_run,
        ) as mock_get_run,
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    # Should return immediately without sleeping (found itself)
    mock_sleep.assert_not_called()
    mock_get_run.assert_called_once()


@pytest.mark.asyncio
async def test_same_type_lock_proceeds_when_no_other_run_exists(mock_manifest):
    """Test that same-type locking proceeds immediately when no other run exists."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            return_value=None,
        ) as mock_get_run,
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    # Should return immediately without sleeping
    mock_sleep.assert_not_called()
    mock_get_run.assert_called_once()


@pytest.mark.asyncio
async def test_same_type_lock_proceeds_when_other_run_completed(mock_manifest):
    """Test that same-type locking proceeds when another run is already COMPLETED."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())
    other_run_id = str(uuid4())

    completed_run = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.COMPLETED,
        run_id=other_run_id,
    )

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            return_value=completed_run,
        ) as mock_get_run,
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    # Should return immediately without sleeping
    mock_sleep.assert_not_called()
    mock_get_run.assert_called_once()


@pytest.mark.asyncio
async def test_no_same_type_lock_when_no_run_id_provided(mock_manifest):
    """Test that same-type locking is disabled when current_workflow_run_id is None."""
    project_id = str(uuid4())

    # Even if there's a RUNNING workflow, it should NOT wait because
    # current_workflow_run_id is not provided
    running_run = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.RUNNING,
    )

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            return_value=running_run,
        ) as mock_get_run,
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        # No current_workflow_run_id = no same-type locking
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            project_id,
            current_workflow_run_id=None,
        )

    # Should return immediately - same-type check is skipped
    mock_sleep.assert_not_called()
    # Should NOT query for same-type runs when no run_id provided and no dependencies
    mock_get_run.assert_not_called()


@pytest.mark.asyncio
async def test_waits_for_both_same_type_and_dependencies():
    """Test that function waits for both same-type lock AND dependencies."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())
    other_run_id = str(uuid4())

    # Manifest with a required dependency
    manifest = MagicMock()
    manifest.required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    manifest.optional_dependencies = []

    # Same-type run is RUNNING
    same_type_running = create_workflow_run(
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunStatus.RUNNING,
        run_id=other_run_id,
    )
    # Dependency is also RUNNING
    dep_running = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.RUNNING,
    )

    call_count = 0

    async def mock_get_run(proj_id, workflow_type):
        nonlocal call_count
        call_count += 1
        if workflow_type == WorkflowRunType.REFERENCE_EXTRACTION:
            # Same-type: first RUNNING, then COMPLETED
            if call_count <= 2:
                return same_type_running
            return create_workflow_run(
                WorkflowRunType.REFERENCE_EXTRACTION,
                WorkflowRunStatus.COMPLETED,
                run_id=other_run_id,
            )
        else:
            # Dependency: RUNNING until call 4, then COMPLETED
            if call_count <= 4:
                return dep_running
            return create_workflow_run(
                WorkflowRunType.DOCUMENT_PROCESSING,
                WorkflowRunStatus.COMPLETED,
            )

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.REFERENCE_EXTRACTION,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    # Should have called sleep multiple times waiting for blockers
    assert mock_sleep.call_count >= 2


@pytest.mark.asyncio
async def test_wait_for_dependencies_substitutes_claim_dep_for_v1():
    """V1 should substitute CLAIM_EXTRACTION_V2 dependency with CLAIM_EXTRACTION."""
    project_id = str(uuid4())

    manifest = MagicMock()
    manifest.required_dependencies = [WorkflowRunType.CLAIM_EXTRACTION_V2]
    manifest.optional_dependencies = []

    async def mock_get_run(proj_id, workflow_type):
        if workflow_type == WorkflowRunType.CLAIM_EXTRACTION:
            return create_workflow_run(
                WorkflowRunType.CLAIM_EXTRACTION,
                WorkflowRunStatus.COMPLETED,
            )
        # Ensure we never require CLAIM_EXTRACTION_V2 for v1
        if workflow_type == WorkflowRunType.CLAIM_EXTRACTION_V2:
            return None
        return None

    with (
        patch(
            "api.services.workflow_orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "api.services.workflow_orchestration.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch("api.services.workflow_orchestration.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            project_id,
            current_workflow_run_id=None,
            claim_extraction_version=ClaimExtractionVersion.V1,
        )

    # Should proceed without waiting because substituted dependency is already completed
    mock_sleep.assert_not_called()

