"""
Feedback service layer.

Business logic for feedback CRUD on issues.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue
from lib.models.project import AccessLevel, FeedbackVisibility, Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.projects.service import get_project_access


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


async def _get_owned_issue(
    session: AsyncSession, issue_id: uuid.UUID, user: User
) -> Issue:
    """The issue, once the user is confirmed to own its run. 404s, then 403s."""
    issue = (
        await session.execute(select(Issue).where(col(Issue.id) == issue_id))
    ).scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    await _verify_workflow_run_ownership(session, issue.workflow_run_id, user)
    return issue


async def create_or_update_feedback(
    session: AsyncSession,
    issue_id: uuid.UUID,
    feedback_type: FeedbackType,
    user: User,
    feedback_text: str | None = None,
) -> Feedback:
    """Save the user's feedback on an issue, replacing any they already left.

    The feedback's `workflow_run_id` is taken from the issue.

    Raises:
        HTTPException: 404 if the issue or its run is missing, 403 if the user
            doesn't own the run.
    """
    issue = await _get_owned_issue(session, issue_id, user)

    stmt = (
        select(Feedback)
        .where(col(Feedback.issue_id) == issue_id)
        .where(col(Feedback.user_id) == user.id)
    )
    feedback = (await session.execute(stmt)).scalar_one_or_none()

    if feedback is None:
        feedback = Feedback(
            workflow_run_id=issue.workflow_run_id,
            user_id=user.id,
            issue_id=issue_id,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
        )
    else:
        feedback.feedback_type = feedback_type
        feedback.feedback_text = feedback_text

    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def get_feedback_by_issue(
    session: AsyncSession, issue_id: uuid.UUID, user: User
) -> Feedback | None:
    """The user's feedback on an issue, or None if they haven't rated it.

    Raises:
        HTTPException: 404 if the issue or its run is missing, 403 if the user
            doesn't own the run.
    """
    await _get_owned_issue(session, issue_id, user)

    feedback_stmt = (
        select(Feedback)
        .where(col(Feedback.issue_id) == issue_id)
        .where(col(Feedback.user_id) == user.id)
    )
    feedback_result = await session.execute(feedback_stmt)
    return feedback_result.scalar_one_or_none()


async def get_project_issue_feedback(
    session: AsyncSession, project_id: uuid.UUID, user: User
) -> list[Feedback]:
    """
    Get all issue feedback for a project in one query.

    Owners get their own feedback. Admins get the project's, so that a project shared
    with them shows the ratings its author left rather than an empty margin — the same
    feedback the admin feedback page already lists for it.

    Args:
        session: Database session
        project_id: The project ID
        user: The user requesting the feedback

    Returns:
        List of Feedback objects for all issues in the project
    """
    # The central gate already says who may see a project: its owner, and an admin once
    # the owner has shared it as full_project. Deciding that again here is how the two
    # drift apart.
    _, access_level = await get_project_access(str(project_id), user=user)

    feedback_stmt = (
        select(Feedback)
        .join(Issue, col(Feedback.issue_id) == col(Issue.id))
        .where(col(Issue.project_id) == project_id)
    )
    if access_level == AccessLevel.WRITE:
        feedback_stmt = feedback_stmt.where(col(Feedback.user_id) == user.id)

    feedback_result = await session.execute(feedback_stmt)
    return list(feedback_result.scalars().all())


async def get_admin_feedbacks(
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
    workflow_type: str | None = None,
    feedback_type: FeedbackType | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """
    Get all shared feedback for admin view.

    Returns feedback where the project has feedback_visibility set to
    issue_only or full_project. Filters private feedback out entirely.
    """
    stmt = (
        select(Feedback, Issue, Project, User, WorkflowRun)
        .join(Issue, col(Feedback.issue_id) == col(Issue.id))
        .join(WorkflowRun, col(Feedback.workflow_run_id) == col(WorkflowRun.id))
        .join(Project, col(WorkflowRun.project_id) == col(Project.id))
        .join(User, col(Feedback.user_id) == col(User.id))
        .where(col(Project.feedback_visibility).isnot(None))
        .where(col(Project.feedback_visibility) != FeedbackVisibility.PRIVATE)
    )

    if user_id is not None:
        stmt = stmt.where(col(Feedback.user_id) == user_id)
    if workflow_type is not None:
        stmt = stmt.where(col(Issue.workflow_type) == workflow_type)
    if feedback_type is not None:
        stmt = stmt.where(col(Feedback.feedback_type) == feedback_type)
    if search is not None:
        for token in search.split():
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    col(Issue.title).ilike(pattern),
                    col(Issue.description).ilike(pattern),
                    col(Issue.long_description).ilike(pattern),
                    col(Project.title).ilike(pattern),
                    col(User.name).ilike(pattern),
                    col(User.email).ilike(pattern),
                    col(Feedback.feedback_text).ilike(pattern),
                )
            )

    stmt = stmt.order_by(col(Feedback.created_at).desc())
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    rows = result.all()

    items = []
    for row in rows:
        feedback, issue, project, user, workflow_run = row.tuple()
        items.append(
            {
                "feedback": feedback,
                "issue": issue,
                "project": project,
                "user": user,
                "workflow_run": workflow_run,
            }
        )
    return items


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
