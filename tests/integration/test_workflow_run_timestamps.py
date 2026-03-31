"""Integration tests for started_at and completed_at timestamps on WorkflowRun."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs import create_workflow_run, update_workflow_run_status


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
