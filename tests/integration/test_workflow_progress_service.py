"""Integration tests for workflow progress service."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_progress import ProgressLevel, WorkflowProgress
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_progress import (
    cancel_workflow_progress,
    complete_progress,
    create_and_start_progress,
    get_or_create_progress,
    get_workflow_progress,
    increment_and_complete_if_done,
    update_progress,
)


@pytest_asyncio.fixture
async def workflow_run_id():
    """Create a test workflow run with a real DB entry."""
    run_id = uuid.uuid4()
    thread_id = str(uuid.uuid4())

    async with get_async_db_session() as session:
        workflow_run = WorkflowRun(
            id=run_id,
            langgraph_thread_id=thread_id,
            project_id=None,  # No project needed for test
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            status=WorkflowRunStatus.RUNNING,
        )
        session.add(workflow_run)
        await session.commit()

    yield run_id

    # Cleanup: delete the workflow run (will cascade to progress entries)
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run:
            await session.delete(run)
            await session.commit()


@pytest.mark.asyncio
async def test_create_and_start_progress(workflow_run_id):
    """Test creating and starting a progress entry."""
    # Create progress entry
    progress_id = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
        total_steps=10,
    )

    assert progress_id is not None
    assert isinstance(progress_id, uuid.UUID)

    # Verify it was created and started
    progress_list = await get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 1

    progress = progress_list[0]
    assert progress.name == "Test Node"
    assert progress.level == ProgressLevel.NODE
    assert progress.total_steps == 10
    assert progress.current_step == 0
    assert progress.started_at is not None
    assert progress.completed_at is None
    assert progress.status == "in_progress"


@pytest.mark.asyncio
async def test_update_progress_steps(workflow_run_id):
    """Test updating progress step counters."""
    # Create progress entry
    progress_id = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Test Task",
        level=ProgressLevel.TASK,
        total_steps=100,
    )

    # Update current step
    await update_progress(progress_id, current_step=50)

    # Verify update
    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 50
    assert progress.total_steps == 100

    # Update total steps
    await update_progress(progress_id, total_steps=150)

    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 50
    assert progress.total_steps == 150


@pytest.mark.asyncio
async def test_complete_progress(workflow_run_id):
    """Test completing a progress entry."""
    # Create progress entry
    progress_id = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
        total_steps=5,
    )

    # Update to partial completion
    await update_progress(progress_id, current_step=3)

    # Complete progress
    await complete_progress(progress_id)

    # Verify completion
    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.completed_at is not None
    assert progress.current_step == progress.total_steps
    assert progress.status == "completed"


@pytest.mark.asyncio
async def test_get_workflow_progress_ordering(workflow_run_id):
    """Test that progress entries are returned in creation order."""
    # Create multiple progress entries
    id1 = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="First Node",
        level=ProgressLevel.NODE,
    )

    id2 = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Second Node",
        level=ProgressLevel.NODE,
    )

    id3 = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Third Node",
        level=ProgressLevel.NODE,
    )

    # Get progress list
    progress_list = await get_workflow_progress(workflow_run_id)

    # Verify order
    assert len(progress_list) == 3
    assert progress_list[0].name == "First Node"
    assert progress_list[1].name == "Second Node"
    assert progress_list[2].name == "Third Node"


@pytest.mark.asyncio
async def test_get_or_create_progress_creates_new(workflow_run_id):
    """Test get_or_create_progress creates a new entry when none exists."""
    progress_id = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="New Parallel Node",
        level=ProgressLevel.NODE,
    )

    assert progress_id is not None
    assert isinstance(progress_id, uuid.UUID)

    # Verify it was created with total_steps=1
    progress_list = await get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 1

    progress = progress_list[0]
    assert progress.name == "New Parallel Node"
    assert progress.level == ProgressLevel.NODE
    assert progress.total_steps == 1
    assert progress.current_step == 0
    assert progress.started_at is not None
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_get_or_create_progress_joins_existing(workflow_run_id):
    """Test get_or_create_progress joins existing active entry with same name."""
    # First call creates the entry
    progress_id_1 = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Parallel Node",
        level=ProgressLevel.NODE,
    )

    # Second call should join the existing entry
    progress_id_2 = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Parallel Node",
        level=ProgressLevel.NODE,
    )

    # Third call should also join
    progress_id_3 = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Parallel Node",
        level=ProgressLevel.NODE,
    )

    # All should return the same progress_id
    assert progress_id_1 == progress_id_2 == progress_id_3

    # Verify only one entry was created with total_steps=3
    progress_list = await get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 1

    progress = progress_list[0]
    assert progress.name == "Parallel Node"
    assert progress.total_steps == 3
    assert progress.current_step == 0


@pytest.mark.asyncio
async def test_get_or_create_progress_different_names(workflow_run_id):
    """Test get_or_create_progress creates separate entries for different names."""
    progress_id_a = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Node A",
        level=ProgressLevel.NODE,
    )

    progress_id_b = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Node B",
        level=ProgressLevel.NODE,
    )

    # Should be different progress entries
    assert progress_id_a != progress_id_b

    # Verify two entries were created
    progress_list = await get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 2


@pytest.mark.asyncio
async def test_get_or_create_progress_ignores_completed(workflow_run_id):
    """Test get_or_create_progress creates new entry if existing one is completed."""
    # Create and complete an entry
    progress_id_1 = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Completable Node",
        level=ProgressLevel.NODE,
    )
    await complete_progress(progress_id_1)

    # Now get_or_create should create a new entry (not join the completed one)
    progress_id_2 = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Completable Node",
        level=ProgressLevel.NODE,
    )

    # Should be different progress entries
    assert progress_id_1 != progress_id_2

    # Verify two entries exist
    progress_list = await get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 2


@pytest.mark.asyncio
async def test_increment_and_complete_if_done_increments(workflow_run_id):
    """Test increment_and_complete_if_done increments current_step."""
    # Create entry with total_steps=3
    progress_id = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )
    # Join twice more to get total_steps=3
    await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )
    await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )

    # First increment
    completed = await increment_and_complete_if_done(progress_id)
    assert completed is False

    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 1
    assert progress.completed_at is None

    # Second increment
    completed = await increment_and_complete_if_done(progress_id)
    assert completed is False

    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 2
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_increment_and_complete_if_done_completes(workflow_run_id):
    """Test increment_and_complete_if_done completes when current >= total."""
    # Create entry with total_steps=2
    progress_id = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )
    await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )

    # First increment - should not complete
    completed = await increment_and_complete_if_done(progress_id)
    assert completed is False

    # Second increment - should complete
    completed = await increment_and_complete_if_done(progress_id)
    assert completed is True

    # Verify completion
    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 2
    assert progress.total_steps == 2
    assert progress.completed_at is not None
    assert progress.status == "completed"


@pytest.mark.asyncio
async def test_increment_and_complete_single_step(workflow_run_id):
    """Test increment_and_complete_if_done works for single-step progress."""
    # Create entry with total_steps=1
    progress_id = await get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Single Step Node",
        level=ProgressLevel.NODE,
    )

    # Should complete on first increment
    completed = await increment_and_complete_if_done(progress_id)
    assert completed is True

    # Verify completion
    progress_list = await get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 1
    assert progress.total_steps == 1
    assert progress.completed_at is not None
    assert progress.status == "completed"


@pytest.mark.asyncio
async def test_increment_and_complete_nonexistent_progress():
    """Test increment_and_complete_if_done handles nonexistent progress gracefully."""
    fake_id = uuid.uuid4()
    completed = await increment_and_complete_if_done(fake_id)
    assert completed is False


# ---------------------------------------------------------------------------
# cancel_workflow_progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_workflow_progress_completes_incomplete_entries(workflow_run_id):
    """All incomplete progress entries are stamped with completed_at."""
    # Create two incomplete entries
    await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Node A",
        level=ProgressLevel.NODE,
        total_steps=5,
    )
    await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Node B",
        level=ProgressLevel.NODE,
        total_steps=3,
    )

    await cancel_workflow_progress(workflow_run_id)

    entries = await get_workflow_progress(workflow_run_id)
    assert len(entries) == 2
    for entry in entries:
        assert entry.completed_at is not None, f"Entry {entry.name!r} should have completed_at set"


@pytest.mark.asyncio
async def test_cancel_workflow_progress_is_noop_when_all_already_complete(workflow_run_id):
    """If all entries are already complete, cancel_workflow_progress does not raise."""
    progress_id = await create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Done Node",
        level=ProgressLevel.NODE,
        total_steps=1,
    )
    await complete_progress(progress_id)

    # Should not raise even though there's nothing left to complete
    await cancel_workflow_progress(workflow_run_id)

    entries = await get_workflow_progress(workflow_run_id)
    assert entries[0].completed_at is not None


@pytest.mark.asyncio
async def test_cancel_workflow_progress_only_affects_target_run(workflow_run_id):
    """Entries from a different workflow run are not touched."""
    # Create a second independent workflow run
    other_run_id = uuid.uuid4()
    async with get_async_db_session() as session:
        from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
        other_run = WorkflowRun(
            id=other_run_id,
            langgraph_thread_id=str(uuid.uuid4()),
            project_id=None,
            type=WorkflowRunType.REFERENCE_EXTRACTION,
            status=WorkflowRunStatus.RUNNING,
        )
        session.add(other_run)
        await session.commit()

    try:
        # Create one incomplete entry on each run
        await create_and_start_progress(
            workflow_run_id=workflow_run_id,
            name="Target Node",
            level=ProgressLevel.NODE,
            total_steps=2,
        )
        await create_and_start_progress(
            workflow_run_id=other_run_id,
            name="Other Node",
            level=ProgressLevel.NODE,
            total_steps=2,
        )

        await cancel_workflow_progress(workflow_run_id)

        target_entries = await get_workflow_progress(workflow_run_id)
        other_entries = await get_workflow_progress(other_run_id)

        assert target_entries[0].completed_at is not None
        assert other_entries[0].completed_at is None
    finally:
        async with get_async_db_session() as session:
            from sqlalchemy import select
            from sqlmodel import col
            stmt = select(WorkflowRun).where(col(WorkflowRun.id) == other_run_id)
            run = (await session.execute(stmt)).scalar_one_or_none()
            if run:
                await session.delete(run)
                await session.commit()
