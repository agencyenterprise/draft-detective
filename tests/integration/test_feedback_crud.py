"""Feedback writes: the upsert key, the ownership gate and delete.

The upsert finds an existing row by issue and user, and takes the run from the
issue, so these run against Postgres rather than mocks.
"""

import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue, IssueStatus
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services import feedback_service
from lib.services.workflow_runs.access import get_accessible_workflow_run
from lib.workflows.models import SeverityEnum


async def _add(record: object) -> None:
    async with get_async_db_session() as session:
        session.add(record)
        await session.commit()


async def _delete(model, record_id: uuid.UUID) -> None:
    async with get_async_db_session() as session:
        existing = await session.get(model, record_id)
        if existing:
            await session.delete(existing)
            await session.commit()


async def _feedback_rows(workflow_run_id: uuid.UUID) -> list[Feedback]:
    async with get_async_db_session() as session:
        stmt = select(Feedback).where(col(Feedback.workflow_run_id) == workflow_run_id)
        return list((await session.execute(stmt)).scalars().all())


async def _make_user() -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4()}@example.com",
        name="Test User",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    await _add(user)
    return user


def _make_issue(run: WorkflowRun, title: str) -> Issue:
    return Issue(
        id=uuid.uuid4(),
        project_id=run.project_id,
        workflow_run_id=run.id,
        issue_hash=str(uuid.uuid4()),
        title=title,
        description="A short description.",
        severity=SeverityEnum.HIGH,
        workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
        status=IssueStatus.ACTIVE,
    )


@pytest_asyncio.fixture
async def author():
    user = await _make_user()
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def stranger():
    user = await _make_user()
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def run(author):
    """A completed run on a project the author owns; every feedback row written
    against it is removed afterwards."""
    project = Project(id=uuid.uuid4(), title="Feedback Project", user_id=author.id)
    await _add(project)
    record = WorkflowRun(
        id=uuid.uuid4(),
        project_id=project.id,
        type=WorkflowRunType.RECOMMENDATION_CHECK,
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.COMPLETED,
    )
    await _add(record)

    yield record

    async with get_async_db_session() as session:
        await session.execute(
            delete(Feedback).where(col(Feedback.workflow_run_id) == record.id)
        )
        await session.execute(
            delete(Issue).where(col(Issue.workflow_run_id) == record.id)
        )
        await session.commit()
    await _delete(WorkflowRun, record.id)
    await _delete(Project, project.id)


@pytest_asyncio.fixture
async def issues(run):
    """Two issues on the same run, so only issue_id tells their feedback apart."""
    first, second = _make_issue(run, "First"), _make_issue(run, "Second")
    await _add(first)
    await _add(second)
    return first, second


async def _upsert(
    issue: Issue,
    user: User,
    feedback_type: FeedbackType,
    feedback_text: str | None = None,
) -> Feedback:
    async with get_async_db_session() as session:
        return await feedback_service.create_or_update_feedback(
            session=session,
            issue_id=issue.id,
            feedback_type=feedback_type,
            user=user,
            feedback_text=feedback_text,
        )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_feedback_is_updated_in_place(run, author, issues):
    issue, _ = issues
    first = await _upsert(
        issue, author, FeedbackType.THUMBS_DOWN, feedback_text="wrong page"
    )
    second = await _upsert(issue, author, FeedbackType.THUMBS_UP)

    assert second.id == first.id
    rows = await _feedback_rows(run.id)
    assert len(rows) == 1
    assert rows[0].feedback_type == FeedbackType.THUMBS_UP
    assert rows[0].feedback_text is None


@pytest.mark.asyncio
async def test_feedback_takes_its_run_from_the_issue(run, author, issues):
    issue, _ = issues
    created = await _upsert(issue, author, FeedbackType.THUMBS_UP)

    assert created.workflow_run_id == run.id


@pytest.mark.asyncio
async def test_each_issue_on_a_run_keeps_its_own_feedback(run, author, issues):
    first_issue, second_issue = issues
    await _upsert(first_issue, author, FeedbackType.THUMBS_UP)
    await _upsert(second_issue, author, FeedbackType.THUMBS_DOWN)

    by_issue = {row.issue_id: row.feedback_type for row in await _feedback_rows(run.id)}
    assert by_issue == {
        first_issue.id: FeedbackType.THUMBS_UP,
        second_issue.id: FeedbackType.THUMBS_DOWN,
    }


# ---------------------------------------------------------------------------
# Ownership gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_stranger_cannot_rate_someone_elses_issue(run, stranger, issues):
    issue, _ = issues
    with pytest.raises(HTTPException) as excinfo:
        await _upsert(issue, stranger, FeedbackType.THUMBS_UP)

    assert excinfo.value.status_code == 403
    assert await _feedback_rows(run.id) == []


@pytest.mark.asyncio
async def test_rating_an_unknown_issue_is_a_404(author):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.create_or_update_feedback(
                session=session,
                issue_id=uuid.uuid4(),
                feedback_type=FeedbackType.THUMBS_UP,
                user=author,
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_authorization_does_not_hold_the_callers_connection(run, author, issues):
    """The gate opens its own sessions. If the caller's session already held a
    connection then, each request would need two at once, and a burst the size
    of the pool would starve itself."""
    issue, _ = issues
    for call in (
        lambda session: feedback_service.create_or_update_feedback(
            session=session,
            issue_id=issue.id,
            feedback_type=FeedbackType.THUMBS_UP,
            user=author,
        ),
        lambda session: feedback_service.get_feedback_by_issue(
            session=session, issue_id=issue.id, user=author
        ),
    ):
        async with get_async_db_session() as session:

            async def gate(*args, caller=session, **kwargs):
                assert not caller.in_transaction()
                return await get_accessible_workflow_run(*args, **kwargs)

            with patch.object(feedback_service, "get_accessible_workflow_run", gate):
                await call(session)


# ---------------------------------------------------------------------------
# Feedback by issue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_by_issue_returns_the_authors_row(run, author, issues):
    first_issue, second_issue = issues
    created = await _upsert(first_issue, author, FeedbackType.THUMBS_UP)

    async with get_async_db_session() as session:
        found = await feedback_service.get_feedback_by_issue(
            session=session, issue_id=first_issue.id, user=author
        )
        unrated = await feedback_service.get_feedback_by_issue(
            session=session, issue_id=second_issue.id, user=author
        )

    assert found is not None and found.id == created.id
    assert unrated is None


@pytest.mark.asyncio
async def test_feedback_by_issue_refuses_a_stranger(run, stranger, issues):
    issue, _ = issues
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.get_feedback_by_issue(
                session=session, issue_id=issue.id, user=stranger
            )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_feedback_by_unknown_issue_is_a_404(author):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.get_feedback_by_issue(
                session=session, issue_id=uuid.uuid4(), user=author
            )

    assert excinfo.value.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_author_deletes_their_feedback(run, author, issues):
    created = await _upsert(issues[0], author, FeedbackType.THUMBS_UP)

    async with get_async_db_session() as session:
        deleted = await feedback_service.delete_feedback(
            session=session, feedback_id=created.id, user=author
        )

    assert deleted is True
    assert await _feedback_rows(run.id) == []


@pytest.mark.asyncio
async def test_deleting_someone_elses_feedback_is_refused(
    run, author, stranger, issues
):
    created = await _upsert(issues[0], author, FeedbackType.THUMBS_UP)

    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.delete_feedback(
                session=session, feedback_id=created.id, user=stranger
            )

    assert excinfo.value.status_code == 403
    assert [row.id for row in await _feedback_rows(run.id)] == [created.id]


@pytest.mark.asyncio
async def test_deleting_unknown_feedback_returns_false(author):
    async with get_async_db_session() as session:
        deleted = await feedback_service.delete_feedback(
            session=session, feedback_id=uuid.uuid4(), user=author
        )

    assert deleted is False
