"""Integration tests for workflow progress service."""

import uuid

import pytest

from lib.config.database import get_db
from lib.models.workflow_progress import ProgressLevel, WorkflowProgress
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_progress import (
    complete_progress,
    create_and_start_progress,
    get_workflow_progress,
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
