"""
Issue persistence service.

Handles persisting issues after workflow completion, archiving old issues,
and managing issue resolution.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from sqlalchemy import select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.issue import Issue, IssueStatus
from lib.services.text_sanitization import strip_control_chars
from lib.workflows.models import DocumentIssue, WorkflowRunType

logger = logging.getLogger(__name__)


def _strip_control_chars(text: Optional[str]) -> Optional[str]:
    """Remove C0/C1 control characters that PostgreSQL text columns reject."""
    if text is None:
        return None
    return strip_control_chars(text)


async def persist_workflow_issues(
    workflow_run_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_type: WorkflowRunType,
    issues: List[DocumentIssue],
    checkpoint_id: Optional[str] = None,
    revision: int = 1,
) -> List[Issue]:
    """
    Persist issues from a completed workflow.

    Archives existing active issues of the same workflow type for the project
    and revision, then creates new issues from the provided DocumentIssue list.
    """
    async with get_async_db_session() as session:
        await session.execute(
            update(Issue)
            .where(
                col(Issue.project_id) == project_id,
                col(Issue.workflow_type) == workflow_type.value,
                col(Issue.status) == IssueStatus.ACTIVE,
                col(Issue.revision) == revision,
            )
            .values(status=IssueStatus.ARCHIVED)
        )

        created_issues: List[Issue] = []
        for doc_issue in issues:
            issue = Issue(
                project_id=project_id,
                workflow_run_id=workflow_run_id,
                langgraph_checkpoint_id=checkpoint_id,
                issue_hash=doc_issue.id,
                title=_strip_control_chars(doc_issue.title),
                description=_strip_control_chars(doc_issue.description),
                long_description=_strip_control_chars(doc_issue.long_description),
                severity=doc_issue.severity,
                workflow_type=doc_issue.type,
                chunk_indices=doc_issue.chunk_indices,
                status=IssueStatus.ACTIVE,
                revision=revision,
            )
            session.add(issue)
            created_issues.append(issue)

        await session.commit()

        for issue in created_issues:
            await session.refresh(issue)

        logger.info(
            f"Persisted {len(created_issues)} issues for project {project_id}, "
            f"workflow type {workflow_type.value}"
        )

        return created_issues


async def get_project_issues(
    project_id: uuid.UUID,
    revision: int,
    include_archived: bool = False,
    workflow_types: Optional[List[WorkflowRunType]] = None,
) -> Sequence[Issue]:
    """Get issues for a project and revision."""
    async with get_async_db_session() as session:
        stmt = select(Issue).where(
            col(Issue.project_id) == project_id,
            col(Issue.revision) == revision,
        )

        if not include_archived:
            stmt = stmt.where(col(Issue.status) != IssueStatus.ARCHIVED)

        if workflow_types:
            type_values = [t.value for t in workflow_types]
            stmt = stmt.where(col(Issue.workflow_type).in_(type_values))

        stmt = stmt.order_by(
            col(Issue.resolved_by).asc().nulls_first(),
            col(Issue.severity).desc(),
            col(Issue.created_at).desc(),
        )

        result = await session.execute(stmt)
        return result.scalars().all()


async def get_issue_by_id(issue_id: uuid.UUID) -> Optional[Issue]:
    """Get a single issue by ID."""
    async with get_async_db_session() as session:
        stmt = select(Issue).where(col(Issue.id) == issue_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def resolve_issue(issue_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Issue]:
    """Mark an issue as resolved by a user."""
    async with get_async_db_session() as session:
        stmt = select(Issue).where(col(Issue.id) == issue_id)
        result = await session.execute(stmt)
        issue = result.scalar_one_or_none()

        if issue is None:
            return None

        if issue.status == IssueStatus.ARCHIVED:
            logger.warning(f"Cannot resolve archived issue {issue_id}")
            return issue

        issue.resolved_by = user_id
        issue.resolved_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(issue)

        logger.info(f"Resolved issue {issue_id} by user {user_id}")
        return issue


async def unresolve_issue(issue_id: uuid.UUID) -> Optional[Issue]:
    """Mark an issue as unresolved."""
    async with get_async_db_session() as session:
        stmt = select(Issue).where(col(Issue.id) == issue_id)
        result = await session.execute(stmt)
        issue = result.scalar_one_or_none()

        if issue is None:
            return None

        if issue.status == IssueStatus.ARCHIVED:
            logger.warning(f"Cannot unresolve archived issue {issue_id}")
            return issue

        issue.resolved_by = None
        issue.resolved_at = None
        await session.commit()
        await session.refresh(issue)

        logger.info(f"Unresolved issue {issue_id}")
        return issue
