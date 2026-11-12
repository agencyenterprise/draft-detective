"""Tests for workflow orchestration - dependency and same-type locking."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.orchestration import (
    DEPENDENCY_WAIT_TIMEOUT,
    wait_for_dependencies,
    wait_for_runs_to_end,
)
from lib.workflows.models import DependencyWaitTimeoutError, WorkflowCancelledError


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


@pytest.fixture(autouse=True)
def run_ahead():
    """The same-type run ahead, as read while dependencies still block: none
    unless a test says so."""
    with patch(
        "lib.services.workflow_runs.orchestration.get_run_ahead_in_same_type_queue",
        new=AsyncMock(return_value=None),
    ) as mock_run_ahead:
        yield mock_run_ahead


@pytest.fixture(autouse=True)
def claim():
    """The queue claim, made once nothing else blocks: returns the run ahead,
    None (claimed) unless a test says so."""
    with patch(
        "lib.services.workflow_runs.orchestration.claim_same_type_queue_head",
        new=AsyncMock(return_value=None),
    ) as mock_claim:
        yield mock_claim


@pytest.fixture(autouse=True)
def waiting_run_stays_pending():
    """The waiting run's own status, re-read on every poll: PENDING unless a test says otherwise."""
    with patch(
        "lib.services.workflow_runs.orchestration.get_workflow_run_status",
        new=AsyncMock(return_value=WorkflowRunStatus.PENDING),
    ) as mock_status:
        yield mock_status


@pytest.fixture
def mock_manifest():
    """Mock workflow manifest with no dependencies."""
    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = []
    manifest.optional_dependencies = []
    return manifest


@pytest.mark.asyncio
async def test_same_type_lock_waits_while_a_run_is_ahead(claim, mock_manifest):
    """The run polls until no same-type run is ahead of it, then goes."""
    current_run_id = str(uuid4())
    claim.side_effect = [
        create_workflow_run(
            WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.RUNNING
        ),
        None,
    ]

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            str(uuid4()),
            current_workflow_run_id=current_run_id,
        )

    assert claim.await_count == 2
    claim.assert_awaited_with(current_run_id)
    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_type_lock_proceeds_when_no_run_is_ahead(claim, mock_manifest):
    """Which runs count as ahead is the query's job (see the integration tests);
    with none, the run goes without sleeping."""
    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.DOCUMENT_PROCESSING,
            str(uuid4()),
            current_workflow_run_id=str(uuid4()),
        )

    mock_sleep.assert_not_called()
    claim.assert_awaited_once()


@pytest.mark.asyncio
async def test_independent_runs_do_not_wait_for_each_other(
    run_ahead, claim, mock_manifest
):
    """Runs that read only their own inputs skip the same-type lock, so a queued
    request is not left to time out behind long ones."""
    mock_manifest.independent_runs = True
    other_run = create_workflow_run(
        WorkflowRunType.REVIEW_ASSISTANT, WorkflowRunStatus.RUNNING
    )

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            return_value=other_run,
        ) as mock_get_run,
    ):
        await wait_for_dependencies(
            WorkflowRunType.REVIEW_ASSISTANT,
            str(uuid4()),
            current_workflow_run_id=str(uuid4()),
        )

    mock_get_run.assert_not_called()
    run_ahead.assert_not_called()
    claim.assert_not_called()


@pytest.mark.asyncio
async def test_no_same_type_lock_when_no_run_id_provided(
    run_ahead, claim, mock_manifest
):
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
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            return_value=running_run,
        ) as mock_get_run,
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep,
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
    run_ahead.assert_not_called()
    claim.assert_not_called()


@pytest.mark.asyncio
async def test_waits_for_both_same_type_and_dependencies(run_ahead, claim):
    """Test that function waits for both same-type lock AND dependencies."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())

    # Manifest with a required dependency
    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    manifest.optional_dependencies = []

    # A same-type run is ahead for the first poll only; the claim, made once
    # the dependency completes, finds none
    run_ahead.side_effect = [
        create_workflow_run(
            WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.RUNNING
        )
    ] + [None] * 5
    # The dependency is RUNNING for the first two polls, then COMPLETED
    dependency_polls = 0

    async def mock_get_run(proj_id, workflow_type, **kwargs):
        nonlocal dependency_polls
        dependency_polls += 1
        status = (
            WorkflowRunStatus.RUNNING
            if dependency_polls <= 2
            else WorkflowRunStatus.COMPLETED
        )
        return create_workflow_run(workflow_type, status)

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.REFERENCE_EXTRACTION,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    # Slept while the same-type run, then the dependency, held it back, and
    # claimed only once nothing else did
    assert mock_sleep.call_count == 2
    assert run_ahead.await_count == 2
    claim.assert_awaited_once_with(current_run_id)


@pytest.mark.asyncio
async def test_cancelled_required_dependency_raises_workflow_cancelled_error():
    """If a required dependency is CANCELLED, WorkflowCancelledError is raised and the current run is cancelled."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())

    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    manifest.optional_dependencies = []

    cancelled_dep = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.CANCELLED,
    )

    # Same-type check returns None so the same-type lock does not interfere
    async def mock_get_run(proj_id, workflow_type, **kwargs):
        if workflow_type == WorkflowRunType.REFERENCE_EXTRACTION:
            return None
        return cancelled_dep

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.update_workflow_run_status",
            new=AsyncMock(),
        ) as mock_update_status,
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ),
    ):
        with pytest.raises(WorkflowCancelledError):
            await wait_for_dependencies(
                WorkflowRunType.REFERENCE_EXTRACTION,
                project_id,
                current_workflow_run_id=current_run_id,
            )

    mock_update_status.assert_awaited_once_with(
        current_run_id, WorkflowRunStatus.CANCELLED
    )


@pytest.mark.asyncio
async def test_cancelled_optional_dependency_does_not_raise():
    """A CANCELLED optional dependency is silently skipped — the workflow proceeds."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())

    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = []
    manifest.optional_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    cancelled_dep = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.CANCELLED,
    )

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            return_value=cancelled_dep,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep,
    ):
        await wait_for_dependencies(
            WorkflowRunType.REFERENCE_EXTRACTION,
            project_id,
            current_workflow_run_id=current_run_id,
        )

    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# DependencyWaitTimeoutError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_dependencies_raises_after_timeout(mock_manifest):
    """wait_for_dependencies raises DependencyWaitTimeoutError once it has waited longer than DEPENDENCY_WAIT_TIMEOUT."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())
    other_run_id = str(uuid4())

    # A perpetually RUNNING upstream of the same type → wait loop never clears.
    blocking_run = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.RUNNING,
        run_id=other_run_id,
    )

    # First call returns t=0 (start), then jumps past the timeout window so the
    # loop's deadline check fires on the next iteration.
    monotonic_calls = iter([0.0, float(DEPENDENCY_WAIT_TIMEOUT) + 1.0])

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=blocking_run),
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ),
        patch(
            "lib.services.workflow_runs.orchestration.time.monotonic",
            side_effect=lambda: next(monotonic_calls),
        ),
    ):
        with pytest.raises(DependencyWaitTimeoutError) as exc:
            await wait_for_dependencies(
                WorkflowRunType.DOCUMENT_PROCESSING,
                project_id,
                current_workflow_run_id=current_run_id,
            )

    assert "document_processing" in str(exc.value)
    assert str(DEPENDENCY_WAIT_TIMEOUT) in str(exc.value)


# ---------------------------------------------------------------------------
# FAILED upstream is treated as terminal for required dependencies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_required_failed_dependency_cancels_dependent():
    """A FAILED required dependency aborts the dependent run via WorkflowCancelledError."""
    project_id = str(uuid4())
    current_run_id = str(uuid4())

    manifest_with_required = MagicMock()
    manifest_with_required.required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    manifest_with_required.optional_dependencies = []

    failed_dep = create_workflow_run(
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunStatus.FAILED,
    )

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest_with_required,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=failed_dep),
        ),
        patch(
            "lib.services.workflow_runs.orchestration.update_workflow_run_status",
            new=AsyncMock(),
        ) as mock_update,
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ),
    ):
        with pytest.raises(WorkflowCancelledError) as exc:
            await wait_for_dependencies(
                WorkflowRunType.REFERENCE_EXTRACTION,
                project_id,
                current_workflow_run_id=current_run_id,
            )

    assert "failed" in str(exc.value).lower()
    # The dependent itself is moved to CANCELLED so the cascade is consistent.
    mock_update.assert_any_await(current_run_id, WorkflowRunStatus.CANCELLED)


@pytest.mark.asyncio
async def test_required_dependency_awaiting_approval_blocks_until_released():
    """A dependency awaiting a gate is still coming; the dependent waits rather than failing."""
    project_id = str(uuid4())

    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = [WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2]
    manifest.optional_dependencies = []

    call_count = 0

    async def mock_get_run(proj_id, workflow_type, **kwargs):
        nonlocal call_count
        call_count += 1
        status = (
            WorkflowRunStatus.AWAITING_APPROVAL
            if call_count <= 2
            else WorkflowRunStatus.COMPLETED
        )
        return create_workflow_run(
            WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2, status
        )

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            side_effect=mock_get_run,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep,
    ):
        await wait_for_dependencies(WorkflowRunType.REFERENCE_VALIDATION_V2, project_id)

    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_independent_run_cancelled_before_its_task_starts_does_not_start(
    waiting_run_stays_pending, mock_manifest
):
    """A run with nothing to wait for still checks its own status once, so a
    cancel that lands before its task starts is honoured."""
    mock_manifest.independent_runs = True
    waiting_run_stays_pending.return_value = WorkflowRunStatus.CANCELLED

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=mock_manifest,
        ),
        pytest.raises(WorkflowCancelledError, match="cancelled"),
    ):
        await wait_for_dependencies(
            WorkflowRunType.REVIEW_ASSISTANT,
            str(uuid4()),
            current_workflow_run_id=str(uuid4()),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ended_as", [WorkflowRunStatus.CANCELLED, WorkflowRunStatus.FAILED]
)
async def test_run_that_ends_while_waiting_stops_instead_of_starting(
    waiting_run_stays_pending, ended_as
):
    """A run cancelled by the user (or reaped) while it waits must not go on to
    start its graph once the dependency it waited for completes."""
    current_run_id = str(uuid4())
    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    manifest.optional_dependencies = []
    waiting_run_stays_pending.side_effect = [WorkflowRunStatus.PENDING, ended_as]

    dependency_polls = 0

    async def dependency_completes_on_second_poll(proj_id, workflow_type, **kwargs):
        nonlocal dependency_polls
        dependency_polls += 1
        status = (
            WorkflowRunStatus.RUNNING
            if dependency_polls < 2
            else WorkflowRunStatus.COMPLETED
        )
        return create_workflow_run(workflow_type, status)

    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.get_project_workflow_run_by_type",
            side_effect=dependency_completes_on_second_poll,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ),
        pytest.raises(WorkflowCancelledError, match=ended_as.value),
    ):
        await wait_for_dependencies(
            WorkflowRunType.REFERENCE_EXTRACTION,
            str(uuid4()),
            current_workflow_run_id=current_run_id,
        )


# ---------------------------------------------------------------------------
# wait_for_runs_to_end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_runs_to_end_returns_once_every_run_ended_or_vanished():
    statuses = {
        "a": [
            WorkflowRunStatus.PENDING,
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.COMPLETED,
        ],
        "b": [WorkflowRunStatus.RUNNING, WorkflowRunStatus.FAILED],
        "c": [None],
    }

    async def status_of(run_id: str) -> WorkflowRunStatus | None:
        return statuses[run_id].pop(0)

    sleep = AsyncMock()
    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_run_status",
            new=AsyncMock(side_effect=status_of),
        ),
        patch("lib.services.workflow_runs.orchestration.asyncio.sleep", new=sleep),
    ):
        await wait_for_runs_to_end(["a", "b", "c"])

    assert statuses == {"a": [], "b": [], "c": []}
    assert sleep.await_count == 2


@pytest.mark.asyncio
async def test_wait_for_runs_to_end_gives_up_after_the_timeout():
    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_run_status",
            new=AsyncMock(return_value=WorkflowRunStatus.RUNNING),
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep", new=AsyncMock()
        ),
        patch(
            "lib.services.workflow_runs.orchestration.time.monotonic",
            side_effect=[0.0, DEPENDENCY_WAIT_TIMEOUT + 1],
        ),
    ):
        await wait_for_runs_to_end(["a"])
