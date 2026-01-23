"""Integration tests for workflow progress service."""

import uuid

import pytest

from lib.config.database import get_db
from lib.models.workflow_progress import ProgressLevel, WorkflowProgress
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_progress import (
    complete_progress,
    create_and_start_progress,
    get_or_create_progress,
    get_workflow_progress,
    increment_and_complete_if_done,
    update_progress,
)


@pytest.fixture
def workflow_run_id():
    """Create a test workflow run with a real DB entry."""
    run_id = uuid.uuid4()
    thread_id = str(uuid.uuid4())

    with get_db() as db:
        workflow_run = WorkflowRun(
            id=run_id,
            langgraph_thread_id=thread_id,
            project_id=None,  # No project needed for test
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            status=WorkflowRunStatus.RUNNING,
        )
        db.add(workflow_run)
        db.commit()

    yield run_id

    # Cleanup: delete the workflow run (will cascade to progress entries)
    with get_db() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if run:
            db.delete(run)
            db.commit()


def test_create_and_start_progress(workflow_run_id):
    """Test creating and starting a progress entry."""
    # Create progress entry
    progress_id = create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
        total_steps=10,
    )

    assert progress_id is not None
    assert isinstance(progress_id, uuid.UUID)

    # Verify it was created and started
    progress_list = get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 1

    progress = progress_list[0]
    assert progress.name == "Test Node"
    assert progress.level == ProgressLevel.NODE
    assert progress.total_steps == 10
    assert progress.current_step == 0
    assert progress.started_at is not None
    assert progress.completed_at is None
    assert progress.status == "in_progress"


def test_update_progress_steps(workflow_run_id):
    """Test updating progress step counters."""
    # Create progress entry
    progress_id = create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Test Task",
        level=ProgressLevel.TASK,
        total_steps=100,
    )

    # Update current step
    update_progress(progress_id, current_step=50)

    # Verify update
    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 50
    assert progress.total_steps == 100

    # Update total steps
    update_progress(progress_id, total_steps=150)

    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 50
    assert progress.total_steps == 150


def test_complete_progress(workflow_run_id):
    """Test completing a progress entry."""
    # Create progress entry
    progress_id = create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
        total_steps=5,
    )

    # Update to partial completion
    update_progress(progress_id, current_step=3)

    # Complete progress
    complete_progress(progress_id)

    # Verify completion
    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.completed_at is not None
    assert progress.current_step == progress.total_steps
    assert progress.status == "completed"


def test_get_workflow_progress_ordering(workflow_run_id):
    """Test that progress entries are returned in creation order."""
    # Create multiple progress entries
    id1 = create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="First Node",
        level=ProgressLevel.NODE,
    )

    id2 = create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Second Node",
        level=ProgressLevel.NODE,
    )

    id3 = create_and_start_progress(
        workflow_run_id=workflow_run_id,
        name="Third Node",
        level=ProgressLevel.NODE,
    )

    # Get progress list
    progress_list = get_workflow_progress(workflow_run_id)

    # Verify order
    assert len(progress_list) == 3
    assert progress_list[0].name == "First Node"
    assert progress_list[1].name == "Second Node"
    assert progress_list[2].name == "Third Node"


def test_get_or_create_progress_creates_new(workflow_run_id):
    """Test get_or_create_progress creates a new entry when none exists."""
    progress_id = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="New Parallel Node",
        level=ProgressLevel.NODE,
    )

    assert progress_id is not None
    assert isinstance(progress_id, uuid.UUID)

    # Verify it was created with total_steps=1
    progress_list = get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 1

    progress = progress_list[0]
    assert progress.name == "New Parallel Node"
    assert progress.level == ProgressLevel.NODE
    assert progress.total_steps == 1
    assert progress.current_step == 0
    assert progress.started_at is not None
    assert progress.completed_at is None


def test_get_or_create_progress_joins_existing(workflow_run_id):
    """Test get_or_create_progress joins existing active entry with same name."""
    # First call creates the entry
    progress_id_1 = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Parallel Node",
        level=ProgressLevel.NODE,
    )

    # Second call should join the existing entry
    progress_id_2 = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Parallel Node",
        level=ProgressLevel.NODE,
    )

    # Third call should also join
    progress_id_3 = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Parallel Node",
        level=ProgressLevel.NODE,
    )

    # All should return the same progress_id
    assert progress_id_1 == progress_id_2 == progress_id_3

    # Verify only one entry was created with total_steps=3
    progress_list = get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 1

    progress = progress_list[0]
    assert progress.name == "Parallel Node"
    assert progress.total_steps == 3
    assert progress.current_step == 0


def test_get_or_create_progress_different_names(workflow_run_id):
    """Test get_or_create_progress creates separate entries for different names."""
    progress_id_a = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Node A",
        level=ProgressLevel.NODE,
    )

    progress_id_b = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Node B",
        level=ProgressLevel.NODE,
    )

    # Should be different progress entries
    assert progress_id_a != progress_id_b

    # Verify two entries were created
    progress_list = get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 2


def test_get_or_create_progress_ignores_completed(workflow_run_id):
    """Test get_or_create_progress creates new entry if existing one is completed."""
    # Create and complete an entry
    progress_id_1 = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Completable Node",
        level=ProgressLevel.NODE,
    )
    complete_progress(progress_id_1)

    # Now get_or_create should create a new entry (not join the completed one)
    progress_id_2 = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Completable Node",
        level=ProgressLevel.NODE,
    )

    # Should be different progress entries
    assert progress_id_1 != progress_id_2

    # Verify two entries exist
    progress_list = get_workflow_progress(workflow_run_id)
    assert len(progress_list) == 2


def test_increment_and_complete_if_done_increments(workflow_run_id):
    """Test increment_and_complete_if_done increments current_step."""
    # Create entry with total_steps=3
    progress_id = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )
    # Join twice more to get total_steps=3
    get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )
    get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )

    # First increment
    completed = increment_and_complete_if_done(progress_id)
    assert completed is False

    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 1
    assert progress.completed_at is None

    # Second increment
    completed = increment_and_complete_if_done(progress_id)
    assert completed is False

    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 2
    assert progress.completed_at is None


def test_increment_and_complete_if_done_completes(workflow_run_id):
    """Test increment_and_complete_if_done completes when current >= total."""
    # Create entry with total_steps=2
    progress_id = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )
    get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Test Node",
        level=ProgressLevel.NODE,
    )

    # First increment - should not complete
    completed = increment_and_complete_if_done(progress_id)
    assert completed is False

    # Second increment - should complete
    completed = increment_and_complete_if_done(progress_id)
    assert completed is True

    # Verify completion
    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 2
    assert progress.total_steps == 2
    assert progress.completed_at is not None
    assert progress.status == "completed"


def test_increment_and_complete_single_step(workflow_run_id):
    """Test increment_and_complete_if_done works for single-step progress."""
    # Create entry with total_steps=1
    progress_id = get_or_create_progress(
        workflow_run_id=workflow_run_id,
        name="Single Step Node",
        level=ProgressLevel.NODE,
    )

    # Should complete on first increment
    completed = increment_and_complete_if_done(progress_id)
    assert completed is True

    # Verify completion
    progress_list = get_workflow_progress(workflow_run_id)
    progress = progress_list[0]
    assert progress.current_step == 1
    assert progress.total_steps == 1
    assert progress.completed_at is not None
    assert progress.status == "completed"


def test_increment_and_complete_nonexistent_progress():
    """Test increment_and_complete_if_done handles nonexistent progress gracefully."""
    fake_id = uuid.uuid4()
    completed = increment_and_complete_if_done(fake_id)
    assert completed is False
