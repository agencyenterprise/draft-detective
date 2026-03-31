"""Service layer for workflow progress tracking."""

import asyncio
import logging
import uuid
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_progress import ProgressLevel, WorkflowProgress
from lib.models.workflow_run import WorkflowRun

logger = logging.getLogger(__name__)


@lru_cache(maxsize=256)
def _get_progress_lock(workflow_run_id: uuid.UUID, name: str) -> asyncio.Lock:
    """Get or create a lock for a specific (workflow_run_id, name) combination.

    Uses LRU cache to automatically evict old locks and prevent unbounded memory growth.
    """
    return asyncio.Lock()


async def create_and_start_progress(
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
    async with get_async_db_session() as session:
        progress = WorkflowProgress(
            workflow_run_id=workflow_run_id,
            name=name,
            level=level,
            total_steps=total_steps,
            started_at=datetime.utcnow(),
        )
        session.add(progress)
        await session.commit()
        await session.refresh(progress)
        return progress.id


async def get_or_create_progress(
    workflow_run_id: uuid.UUID,
    name: str,
    level: ProgressLevel,
) -> uuid.UUID:
    """
    Get existing active progress entry by name, or create a new one.

    If an active (not completed) progress entry exists with the same
    (workflow_run_id, name), atomically increment its total_steps and return its ID.
    Otherwise, create a new entry with total_steps=1.

    This enables automatic batching of parallel nodes with the same name.

    Uses an asyncio lock to prevent race conditions when multiple parallel nodes
    try to create progress entries simultaneously. The lock serializes access
    so only one coroutine can create/update at a time for a given key.

    Args:
        workflow_run_id: ID of the workflow run
        name: Human-readable name
        level: Progress level (workflow, node, task)

    Returns:
        UUID of the progress entry (existing or newly created)
    """

    lock = _get_progress_lock(workflow_run_id, name)

    async with lock:
        async with get_async_db_session() as session:
            # Find existing active progress with same name
            stmt = select(WorkflowProgress).where(
                col(WorkflowProgress.workflow_run_id) == workflow_run_id,
                col(WorkflowProgress.name) == name,
                col(WorkflowProgress.completed_at).is_(None),
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Increment total_steps for the batch
                existing.total_steps += 1
                await session.commit()
                return existing.id

            # Create new progress entry
            progress = WorkflowProgress(
                workflow_run_id=workflow_run_id,
                name=name,
                level=level,
                total_steps=1,
                started_at=datetime.utcnow(),
            )
            session.add(progress)
            await session.commit()
            await session.refresh(progress)
            return progress.id


async def _get_progress_by_id(
    session: AsyncSession, progress_id: uuid.UUID
) -> Optional[WorkflowProgress]:
    """Get a progress entry by ID."""
    stmt = select(WorkflowProgress).where(col(WorkflowProgress.id) == progress_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_progress(
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
    async with get_async_db_session() as session:
        progress = await _get_progress_by_id(session, progress_id)

        if not progress:
            logger.warning(f"Progress entry {progress_id} not found")
            return

        if current_step is not None:
            progress.current_step = current_step
        if total_steps is not None:
            progress.total_steps = total_steps

        # Note: updated_at is handled by onupdate in the model
        await session.commit()


async def complete_progress(progress_id: uuid.UUID) -> None:
    """
    Mark a progress entry as completed.

    Args:
        progress_id: ID of the progress entry
    """
    async with get_async_db_session() as session:
        progress = await _get_progress_by_id(session, progress_id)

        if not progress:
            logger.warning(f"Progress entry {progress_id} not found")
            return

        progress.completed_at = datetime.utcnow()
        progress.current_step = progress.total_steps
        # Note: updated_at is handled by onupdate in the model
        await session.commit()


async def increment_and_complete_if_done(progress_id: uuid.UUID) -> bool:
    """
    Atomically increment current_step and mark complete if current >= total.

    This is used by the register_node decorator to track progress of parallel
    nodes. Each node calls this when it completes, and the progress is marked
    complete when all parallel nodes have finished.

    Args:
        progress_id: ID of the progress entry

    Returns:
        True if the progress was marked complete, False otherwise
    """
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowProgress)
            .where(col(WorkflowProgress.id) == progress_id)
            .with_for_update()  # Lock row to prevent race conditions
        )
        result = await session.execute(stmt)
        progress = result.scalar_one_or_none()

        if not progress:
            logger.warning(f"Progress entry {progress_id} not found")
            return False

        progress.current_step += 1

        if progress.current_step >= progress.total_steps:
            progress.completed_at = datetime.utcnow()
            await session.commit()
            return True

        await session.commit()
        return False


async def cancel_workflow_progress(workflow_run_id: uuid.UUID) -> None:
    """
    Mark all incomplete progress entries for a workflow run as completed.

    Called when a workflow run is cancelled to prevent progress entries from
    remaining stuck in 'pending' or 'in_progress' state indefinitely.

    Args:
        workflow_run_id: ID of the workflow run being cancelled
    """
    async with get_async_db_session() as session:
        stmt = select(WorkflowProgress).where(
            col(WorkflowProgress.workflow_run_id) == workflow_run_id,
            col(WorkflowProgress.completed_at).is_(None),
        )
        result = await session.execute(stmt)
        incomplete = result.scalars().all()

        now = datetime.utcnow()
        for progress in incomplete:
            progress.completed_at = now

        if incomplete:
            await session.commit()


async def get_workflow_progress(
    workflow_run_id: uuid.UUID,
) -> List[WorkflowProgress]:
    """
    Get all progress entries for a workflow run.

    Args:
        workflow_run_id: ID of the workflow run

    Returns:
        List of progress entries ordered by creation time
    """
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowProgress)
            .where(col(WorkflowProgress.workflow_run_id) == workflow_run_id)
            .order_by(col(WorkflowProgress.created_at))
        )
        result = await session.execute(stmt)
        progress_list = result.scalars().all()
        return list(progress_list)


async def get_project_workflow_progress(
    project_id: uuid.UUID,
) -> List[WorkflowProgress]:
    """
    Get all progress entries for all workflow runs in a project.

    Args:
        project_id: ID of the project

    Returns:
        List of progress entries ordered by creation time
    """
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowProgress)
            .join(
                WorkflowRun,
                col(WorkflowProgress.workflow_run_id) == col(WorkflowRun.id),
            )
            .where(col(WorkflowRun.project_id) == project_id)
            .order_by(col(WorkflowProgress.created_at))
        )
        result = await session.execute(stmt)
        progress_list = result.scalars().all()
        return list(progress_list)
