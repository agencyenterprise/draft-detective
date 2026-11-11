"""Who may read a project's issue feedback.

Owners read their own. Admins read the author's, but only on a project shared as
full_project — the same consent that lets them open the project at all. Everyone else
is refused.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue, IssueStatus
from lib.models.project import FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services import feedback_service
from lib.workflows.models import SeverityEnum


async def _delete(model, record_id) -> None:
    async with get_async_db_session() as session:
        stmt = select(model).where(col(model.id) == record_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


async def _make_user(role: UserRole) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4()}@example.com",
        name="Test User",
        role=role,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    return user


@pytest_asyncio.fixture
async def author():
    """The project's owner — the only one who can leave feedback on it."""
    user = await _make_user(UserRole.USER)
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def admin():
    user = await _make_user(UserRole.ADMIN)
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def stranger():
    user = await _make_user(UserRole.USER)
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def project(author):
    """Shared as full_project, which is what lets an admin open it at all."""
    record = Project(
        id=uuid.uuid4(),
        title="Shared Project",
        user_id=author.id,
        feedback_visibility=FeedbackVisibility.FULL_PROJECT,
    )
    async with get_async_db_session() as session:
        session.add(record)
        await session.commit()
    yield record
    await _delete(Project, record.id)


@pytest_asyncio.fixture
async def feedback(author, project):
    """One thumbs-down from the author, on one issue of one run."""
    run = WorkflowRun(
        id=uuid.uuid4(),
        project_id=project.id,
        type=WorkflowRunType.RECOMMENDATION_CHECK,
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.COMPLETED,
    )
    issue = Issue(
        id=uuid.uuid4(),
        project_id=project.id,
        workflow_run_id=run.id,
        issue_hash=str(uuid.uuid4()),
        title="Test Issue",
        description="A short description.",
        severity=SeverityEnum.HIGH,
        workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
        status=IssueStatus.ACTIVE,
    )
    record = Feedback(
        id=uuid.uuid4(),
        workflow_run_id=run.id,
        user_id=author.id,
        issue_id=issue.id,
        feedback_type=FeedbackType.THUMBS_DOWN,
        feedback_text="not useful",
    )
    # Committed in order: nothing declares an ORM relationship between these, so the
    # session cannot work out that the issue has to land before the feedback pointing
    # at it.
    async with get_async_db_session() as session:
        session.add(run)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(issue)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(record)
        await session.commit()

    yield record

    await _delete(Feedback, record.id)
    await _delete(Issue, issue.id)
    await _delete(WorkflowRun, run.id)


@pytest.mark.asyncio
async def test_author_reads_own_feedback(author, project, feedback):
    async with get_async_db_session() as session:
        rows = await feedback_service.get_project_issue_feedback(
            session=session, project_id=project.id, user=author
        )

    assert [row.id for row in rows] == [feedback.id]


@pytest.mark.asyncio
async def test_admin_reads_the_authors_feedback(admin, project, feedback):
    """The point of the change: an admin sees the ratings the author left, not the
    empty set they would get from filtering on their own user id."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_project_issue_feedback(
            session=session, project_id=project.id, user=admin
        )

    assert [row.id for row in rows] == [feedback.id]
    assert rows[0].feedback_text == "not useful"


@pytest.mark.asyncio
async def test_admin_is_refused_when_the_project_is_not_shared(
    admin, project, feedback
):
    """Visibility is the consent gate. Without full_project an admin gets nothing,
    even though the same admin can see shared feedback on the admin page."""
    async with get_async_db_session() as session:
        stored = await session.get(Project, project.id)
        assert stored is not None
        stored.feedback_visibility = FeedbackVisibility.ISSUE_ONLY
        session.add(stored)
        await session.commit()

    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.get_project_issue_feedback(
                session=session, project_id=project.id, user=admin
            )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_stranger_is_refused(stranger, project, feedback):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.get_project_issue_feedback(
                session=session, project_id=project.id, user=stranger
            )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_project_is_a_404(admin):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.get_project_issue_feedback(
                session=session, project_id=uuid.uuid4(), user=admin
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_cannot_rate_an_issue_on_a_shared_project(admin, feedback):
    """Reading the project is not rating it: rating stays with the owner."""
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.create_or_update_feedback(
                session=session,
                issue_id=feedback.issue_id,
                feedback_type=FeedbackType.THUMBS_UP,
                user=admin,
            )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_read_an_issue_rating_on_a_shared_project(admin, feedback):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await feedback_service.get_feedback_by_issue(
                session=session, issue_id=feedback.issue_id, user=admin
            )

    assert excinfo.value.status_code == 403
