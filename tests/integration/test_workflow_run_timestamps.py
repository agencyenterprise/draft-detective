"""Integration tests for started_at and completed_at timestamps on WorkflowRun."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs import (
    create_workflow_run,
    update_workflow_run_heartbeat,
    update_workflow_run_status,
)


@pytest_asyncio.fixture
async def pending_run_id():
    """Create a PENDING workflow run and clean it up after the test."""
    run_id = uuid.uuid4()

    async with get_async_db_session() as session:
        run = WorkflowRun(
            id=run_id,
            langgraph_thread_id=str(uuid.uuid4()),
            project_id=None,
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            status=WorkflowRunStatus.PENDING,
        )
        session.add(run)
        await session.commit()

    yield str(run_id)

    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
        run = (await session.execute(stmt)).scalar_one_or_none()
        if run:
            await session.delete(run)
            await session.commit()


async def _fetch_run(run_id: str) -> WorkflowRun:
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
        return (await session.execute(stmt)).scalar_one()


# ---------------------------------------------------------------------------
# update_workflow_run_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_started_at_set_when_transitioning_to_running(pending_run_id):
    """started_at is populated when a run transitions to RUNNING."""
    run = await _fetch_run(pending_run_id)
    assert run.started_at is None

    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)

    run = await _fetch_run(pending_run_id)
    assert run.started_at is not None
    assert run.completed_at is None


@pytest.mark.asyncio
async def test_started_at_not_overwritten_on_repeated_running(pending_run_id):
    """started_at is set only once — a second RUNNING transition does not overwrite it."""
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)
    run = await _fetch_run(pending_run_id)
    first_started_at = run.started_at
    assert first_started_at is not None

    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)
    run = await _fetch_run(pending_run_id)
    assert run.started_at == first_started_at


@pytest.mark.asyncio
async def test_completed_at_set_when_transitioning_to_completed(pending_run_id):
    """completed_at is populated when a run transitions to COMPLETED."""
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.COMPLETED)

    run = await _fetch_run(pending_run_id)
    assert run.completed_at is not None
    assert run.started_at is not None


@pytest.mark.asyncio
async def test_completed_at_set_when_transitioning_to_cancelled(pending_run_id):
    """completed_at is populated when a run transitions to CANCELLED."""
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.CANCELLED)

    run = await _fetch_run(pending_run_id)
    assert run.completed_at is not None
    assert run.started_at is not None


@pytest.mark.asyncio
async def test_timestamps_remain_none_for_pending_run(pending_run_id):
    """A run that stays PENDING should have neither timestamp set."""
    run = await _fetch_run(pending_run_id)
    assert run.started_at is None
    assert run.completed_at is None


@pytest.mark.asyncio
async def test_completed_at_not_overwritten_after_cancelled(pending_run_id):
    """
    Once CANCELLED the guard in update_workflow_run_status prevents any further
    status changes, so completed_at should not be overwritten by a subsequent
    COMPLETED transition.
    """
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.CANCELLED)
    run = await _fetch_run(pending_run_id)
    original_completed_at = run.completed_at
    assert original_completed_at is not None

    # This call should be a no-op because the guard blocks CANCELLED overwrites
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.COMPLETED)
    run = await _fetch_run(pending_run_id)
    assert run.completed_at == original_completed_at
    assert run.status == WorkflowRunStatus.CANCELLED


# ---------------------------------------------------------------------------
# create_workflow_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workflow_run_with_completed_status_sets_completed_at():
    """A run inserted directly with COMPLETED status should have completed_at set."""
    run_id = await create_workflow_run(
        project_id=None,
        status=WorkflowRunStatus.COMPLETED,
        type=WorkflowRunType.DOCUMENT_PROCESSING,
        thread_id=str(uuid.uuid4()),
    )

    try:
        run = await _fetch_run(run_id)
        assert run.completed_at is not None
        assert run.started_at is None
    finally:
        async with get_async_db_session() as session:
            stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()


# ---------------------------------------------------------------------------
# FAILED status persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_status_persists_failure_reason_and_message(pending_run_id):
    """Transitioning to FAILED stores failure_reason, failure_message, and completed_at."""
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)
    await update_workflow_run_status(
        pending_run_id,
        WorkflowRunStatus.FAILED,
        failure_reason=WorkflowRunFailureReason.TIMEOUT,
        failure_message="Exceeded max_duration of 3600s",
    )

    run = await _fetch_run(pending_run_id)
    assert run.status == WorkflowRunStatus.FAILED
    assert run.failure_reason == WorkflowRunFailureReason.TIMEOUT
    assert run.failure_message == "Exceeded max_duration of 3600s"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_failed_status_truncates_long_failure_message(pending_run_id):
    """failure_message is capped at 2000 chars to keep the column bounded."""
    long_message = "x" * 5000
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.RUNNING)
    await update_workflow_run_status(
        pending_run_id,
        WorkflowRunStatus.FAILED,
        failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
        failure_message=long_message,
    )

    run = await _fetch_run(pending_run_id)
    assert run.failure_message is not None
    assert len(run.failure_message) == 2000


@pytest.mark.asyncio
async def test_non_failed_status_does_not_persist_failure_metadata(pending_run_id):
    """failure_reason / failure_message are ignored for non-FAILED transitions."""
    await update_workflow_run_status(
        pending_run_id,
        WorkflowRunStatus.RUNNING,
        failure_reason=WorkflowRunFailureReason.TIMEOUT,
        failure_message="should be ignored",
    )

    run = await _fetch_run(pending_run_id)
    assert run.status == WorkflowRunStatus.RUNNING
    assert run.failure_reason is None
    assert run.failure_message is None


@pytest.mark.asyncio
async def test_cancelled_guard_blocks_failed_transition(pending_run_id):
    """Once CANCELLED, a subsequent FAILED transition is a no-op (guard preserved)."""
    await update_workflow_run_status(pending_run_id, WorkflowRunStatus.CANCELLED)
    await update_workflow_run_status(
        pending_run_id,
        WorkflowRunStatus.FAILED,
        failure_reason=WorkflowRunFailureReason.NO_HEARTBEAT,
        failure_message="should not stick",
    )

    run = await _fetch_run(pending_run_id)
    assert run.status == WorkflowRunStatus.CANCELLED
    assert run.failure_reason is None
    assert run.failure_message is None


# ---------------------------------------------------------------------------
# update_workflow_run_heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_update_sets_heartbeat_at(pending_run_id):
    """update_workflow_run_heartbeat populates heartbeat_at without changing status."""
    run = await _fetch_run(pending_run_id)
    assert run.heartbeat_at is None
    original_status = run.status

    await update_workflow_run_heartbeat(pending_run_id)

    run = await _fetch_run(pending_run_id)
    assert run.heartbeat_at is not None
    assert run.status == original_status


@pytest.mark.asyncio
async def test_heartbeat_update_advances_heartbeat_on_repeat(pending_run_id):
    """Repeated heartbeats keep advancing the timestamp."""
    await update_workflow_run_heartbeat(pending_run_id)
    first = (await _fetch_run(pending_run_id)).heartbeat_at
    assert first is not None

    await update_workflow_run_heartbeat(pending_run_id)
    second = (await _fetch_run(pending_run_id)).heartbeat_at
    assert second is not None
    assert second >= first


@pytest.mark.asyncio
async def test_create_workflow_run_with_pending_status_leaves_timestamps_none():
    """A freshly-created PENDING run should have both timestamps as None."""
    run_id = await create_workflow_run(
        project_id=None,
        status=WorkflowRunStatus.PENDING,
        type=WorkflowRunType.DOCUMENT_PROCESSING,
        thread_id=str(uuid.uuid4()),
    )

    try:
        run = await _fetch_run(run_id)
        assert run.started_at is None
        assert run.completed_at is None
    finally:
        async with get_async_db_session() as session:
            stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()
