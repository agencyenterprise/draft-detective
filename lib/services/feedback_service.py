"""
Feedback service layer.

Provides business logic for feedback CRUD operations using coordinate-based addressing.
"""

from typing import Optional
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.models.feedback import Feedback, FeedbackType
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun


async def _verify_workflow_run_ownership(
    session: AsyncSession, workflow_run_id: uuid.UUID, user: User
) -> None:
    """Verify that the user owns the workflow run, raise 403 if not."""
    stmt = (
        select(WorkflowRun, Project)
        .join(Project)
        .where(col(WorkflowRun.id) == workflow_run_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    workflow_run, project = row.tuple()

    if project.user_id is None or project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")


async def create_feedback(
    session: AsyncSession,
    workflow_run_id: uuid.UUID,
    entity_path: dict,
    feedback_type: FeedbackType,
    user: User,
    feedback_text: Optional[str] = None,
) -> Feedback:
    """
    Create new feedback for any entity.

    Args:
        session: Database session
        workflow_run_id: The workflow run this feedback belongs to
        entity_path: Dict with entity coordinates, e.g.:
            - {"chunk_index": 0} for chunk
            - {"chunk_index": 0, "claim_index": 1} for claim
            - {"reference_index": 2} for reference
            - {} for workflow-level feedback
        feedback_type: Type of feedback
        user: The user creating the feedback
        feedback_text: Optional feedback text

    Returns:
        Created Feedback object

    Raises:
        HTTPException: If workflow run not found or user doesn't own it
    """
    await _verify_workflow_run_ownership(session, workflow_run_id, user)

    feedback = Feedback(
        workflow_run_id=workflow_run_id,
        user_id=user.id,
        entity_path=entity_path,
        feedback_type=feedback_type,
        feedback_text=feedback_text,
    )

    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def create_or_update_feedback(
    session: AsyncSession,
    workflow_run_id: uuid.UUID,
    entity_path: dict,
    feedback_type: FeedbackType,
    user: User,
    feedback_text: Optional[str] = None,
) -> Feedback:
    """
    Create or update feedback for any entity.

    If feedback already exists for this entity and user, it will be updated.
    Otherwise, a new feedback entry is created.

    Args:
        session: Database session
        workflow_run_id: The workflow run this feedback belongs to
        entity_path: Dict with entity coordinates
        feedback_type: Type of feedback
        user: The user creating/updating the feedback
        feedback_text: Optional feedback text

    Returns:
        Created or updated Feedback object

    Raises:
        HTTPException: If workflow run not found or user doesn't own it
    """
    await _verify_workflow_run_ownership(session, workflow_run_id, user)

    stmt = (
        select(Feedback)
        .where(col(Feedback.workflow_run_id) == workflow_run_id)
        .where(col(Feedback.user_id) == user.id)
        .where(col(Feedback.entity_path) == entity_path)
    )
    result = await session.execute(stmt)
    existing_feedback = result.scalar_one_or_none()

    if existing_feedback:
        existing_feedback.feedback_type = feedback_type
        existing_feedback.feedback_text = feedback_text
        session.add(existing_feedback)
        await session.commit()
        await session.refresh(existing_feedback)
        return existing_feedback

    return await create_feedback(
        session=session,
        workflow_run_id=workflow_run_id,
        entity_path=entity_path,
        feedback_type=feedback_type,
        user=user,
        feedback_text=feedback_text,
    )


async def get_feedback(
    session: AsyncSession, workflow_run_id: uuid.UUID, entity_path: dict, user: User
) -> Optional[Feedback]:
    """
    Get feedback for a specific entity.

    Args:
        session: Database session
        workflow_run_id: The workflow run ID
        entity_path: Dict with entity coordinates
        user: The user requesting the feedback

    Returns:
        Feedback object if found, None otherwise

    Raises:
        HTTPException: If workflow run not found or user doesn't own it
    """
    await _verify_workflow_run_ownership(session, workflow_run_id, user)

    stmt = (
        select(Feedback)
        .where(col(Feedback.workflow_run_id) == workflow_run_id)
        .where(col(Feedback.user_id) == user.id)
        .where(col(Feedback.entity_path) == entity_path)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_workflow_feedback(
    session: AsyncSession, workflow_run_id: uuid.UUID, user: User
) -> list[Feedback]:
    """
    Get all feedback for a workflow run.

    Args:
        session: Database session
        workflow_run_id: The workflow run ID
        user: The user requesting the feedback

    Returns:
        List of Feedback objects

    Raises:
        HTTPException: If workflow run not found or user doesn't own it
    """
    await _verify_workflow_run_ownership(session, workflow_run_id, user)

    stmt = (
        select(Feedback)
        .where(col(Feedback.workflow_run_id) == workflow_run_id)
        .where(col(Feedback.user_id) == user.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_feedback(
    session: AsyncSession, feedback_id: uuid.UUID, user: User
) -> bool:
    """
    Delete feedback by ID.

    Args:
        session: Database session
        feedback_id: The feedback ID to delete
        user: The user attempting to delete the feedback

    Returns:
        True if feedback was deleted, False if not found

    Raises:
        HTTPException: If user doesn't own the feedback
    """
    stmt = select(Feedback).where(col(Feedback.id) == feedback_id)
    result = await session.execute(stmt)
    feedback = result.scalar_one_or_none()

    if feedback is None:
        return False

    if feedback.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await session.delete(feedback)
    await session.commit()
    return True
