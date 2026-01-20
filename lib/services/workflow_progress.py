"""Service layer for workflow progress tracking."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from lib.config.database import get_db
from lib.models.workflow_progress import ProgressLevel, WorkflowProgress
from lib.models.workflow_run import WorkflowRun

logger = logging.getLogger(__name__)


def create_and_start_progress(
    workflow_run_id: uuid.UUID,
    name: str,
    level: ProgressLevel,
    total_steps: int = 0,
) -> uuid.UUID:
    """
    Create a new progress entry and mark it as started.

    Args:
        workflow_run_id: ID of the workflow run
        name: Human-readable name
        level: Progress level (workflow, node, task)
        total_steps: Total steps to process (default 0, can be updated later)

    Returns:
        UUID of the created progress entry
    """
    with get_db() as db:
        progress = WorkflowProgress(
            workflow_run_id=workflow_run_id,
            name=name,
            level=level,
            total_steps=total_steps,
            started_at=datetime.utcnow(),
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
        return progress.id


def _get_progress_by_id(db, progress_id: uuid.UUID) -> Optional[WorkflowProgress]:
    """Get a progress entry by ID."""
    return db.query(WorkflowProgress).filter(WorkflowProgress.id == progress_id).first()


def update_progress(
    progress_id: uuid.UUID,
    current_step: Optional[int] = None,
    total_steps: Optional[int] = None,
) -> None:
    """
    Update progress step counters.

    Args:
        progress_id: ID of the progress entry
        current_step: Update current step (optional)
        total_steps: Update total steps (optional)
    """
    with get_db() as db:
        progress = _get_progress_by_id(db, progress_id)

        if not progress:
            logger.warning(f"Progress entry {progress_id} not found")
            return

        if current_step is not None:
            progress.current_step = current_step
        if total_steps is not None:
            progress.total_steps = total_steps

        # Note: updated_at is handled by onupdate in the model
        db.commit()


def complete_progress(progress_id: uuid.UUID) -> None:
    """
    Mark a progress entry as completed.

    Args:
        progress_id: ID of the progress entry
    """
    with get_db() as db:
        progress = _get_progress_by_id(db, progress_id)

        if not progress:
            logger.warning(f"Progress entry {progress_id} not found")
            return

        progress.completed_at = datetime.utcnow()
        progress.current_step = progress.total_steps
        # Note: updated_at is handled by onupdate in the model
        db.commit()


def get_workflow_progress(
    workflow_run_id: uuid.UUID,
) -> List[WorkflowProgress]:
    """
    Get all progress entries for a workflow run.

    Args:
        workflow_run_id: ID of the workflow run

    Returns:
        List of progress entries ordered by creation time
    """
    with get_db() as db:
        progress_list = (
            db.query(WorkflowProgress)
            .filter(WorkflowProgress.workflow_run_id == workflow_run_id)
            .order_by(WorkflowProgress.created_at)
            .all()
        )
        return list(progress_list)


def get_project_workflow_progress(project_id: uuid.UUID) -> List[WorkflowProgress]:
    """
    Get all progress entries for all workflow runs in a project.

    Args:
        project_id: ID of the project

    Returns:
        List of progress entries ordered by creation time
    """
    with get_db() as db:
        progress_list = (
            db.query(WorkflowProgress)
            .join(WorkflowRun, WorkflowProgress.workflow_run_id == WorkflowRun.id)
            .filter(WorkflowRun.project_id == project_id)
            .order_by(WorkflowProgress.created_at)
            .all()
        )
        return list(progress_list)
