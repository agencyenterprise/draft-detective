"""Integration tests for the admin feedback export service."""

import uuid

import pytest
import pytest_asyncio
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_user():
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4()}@example.com",
        name="Test User",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()

    yield user

    async with get_async_db_session() as session:
        stmt = select(User).where(col(User.id) == user.id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


@pytest_asyncio.fixture
async def shared_project(db_user):
    """Create a project with IssueOnly feedback visibility."""
    project = Project(
        id=uuid.uuid4(),
        title="Test Project",
        user_id=db_user.id,
        feedback_visibility=FeedbackVisibility.ISSUE_ONLY,
    )
    async with get_async_db_session() as session:
        session.add(project)
        await session.commit()

    yield project

    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == project.id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


@pytest_asyncio.fixture
async def workflow_run(shared_project):
    """Create a test workflow run linked to the project."""
    run = WorkflowRun(
        id=uuid.uuid4(),
        project_id=shared_project.id,
        type=WorkflowRunType.CITATION_DETECTION,
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.COMPLETED,
    )
    async with get_async_db_session() as session:
        session.add(run)
        await session.commit()

    yield run

    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run.id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


@pytest_asyncio.fixture
async def issue(shared_project, workflow_run):
    """Create a test issue."""
    iss = Issue(
        id=uuid.uuid4(),
        project_id=shared_project.id,
        workflow_run_id=workflow_run.id,
        issue_hash=str(uuid.uuid4()),
        title="Test Issue Title",
        description="A short description of the issue.",
        long_description="A longer detailed description.",
        severity=SeverityEnum.HIGH,
        workflow_type=WorkflowRunType.CITATION_DETECTION,
        status=IssueStatus.ACTIVE,
        chunk_indices=[0, 1],
    )
    async with get_async_db_session() as session:
        session.add(iss)
        await session.commit()

    yield iss

    async with get_async_db_session() as session:
        stmt = select(Issue).where(col(Issue.id) == iss.id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


@pytest_asyncio.fixture
async def thumbs_down_feedback(db_user, workflow_run, issue):
    """Create a thumbs-down feedback entry linked to the issue."""
    fb = Feedback(
        id=uuid.uuid4(),
        workflow_run_id=workflow_run.id,
        user_id=db_user.id,
        issue_id=issue.id,
        entity_path={},
        feedback_type=FeedbackType.THUMBS_DOWN,
        feedback_text="This citation is wrong.",
    )
    async with get_async_db_session() as session:
        session.add(fb)
        await session.commit()

    yield fb

    async with get_async_db_session() as session:
        stmt = select(Feedback).where(col(Feedback.id) == fb.id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_admin_feedbacks_returns_shared_feedback(
    thumbs_down_feedback, db_user, shared_project, issue
):
    """Returns feedback when project visibility is not PRIVATE."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(session=session)

    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id in ids

    matching = next(r for r in rows if r["feedback"].id == thumbs_down_feedback.id)
    assert matching["user"].id == db_user.id
    assert matching["project"].id == shared_project.id
    assert matching["issue"].id == issue.id
    assert matching["feedback"].feedback_type == FeedbackType.THUMBS_DOWN
    assert matching["feedback"].feedback_text == "This citation is wrong."


@pytest.mark.asyncio
async def test_get_admin_feedbacks_filters_private_projects(db_user, workflow_run, issue):
    """Feedback from PRIVATE projects is excluded."""
    async with get_async_db_session() as session:
        stmt = select(Project).where(col(Project.id) == workflow_run.project_id)
        result = await session.execute(stmt)
        project = result.scalar_one()
        project.feedback_visibility = FeedbackVisibility.PRIVATE
        session.add(project)
        await session.commit()

    fb = Feedback(
        id=uuid.uuid4(),
        workflow_run_id=workflow_run.id,
        user_id=db_user.id,
        issue_id=issue.id,
        entity_path={},
        feedback_type=FeedbackType.THUMBS_UP,
    )
    async with get_async_db_session() as session:
        session.add(fb)
        await session.commit()

    try:
        async with get_async_db_session() as session:
            rows = await feedback_service.get_admin_feedbacks(session=session)

        ids = [row["feedback"].id for row in rows]
        assert fb.id not in ids
    finally:
        async with get_async_db_session() as session:
            stmt = select(Feedback).where(col(Feedback.id) == fb.id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                await session.delete(existing)

            stmt = select(Project).where(col(Project.id) == workflow_run.project_id)
            result = await session.execute(stmt)
            project = result.scalar_one()
            project.feedback_visibility = FeedbackVisibility.ISSUE_ONLY
            session.add(project)
            await session.commit()


@pytest.mark.asyncio
async def test_get_admin_feedbacks_filter_by_user_id(
    thumbs_down_feedback, db_user, shared_project
):
    """user_id filter returns only that user's feedback."""
    other_user_id = uuid.uuid4()

    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, user_id=db_user.id
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id in ids

    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, user_id=other_user_id
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id not in ids


@pytest.mark.asyncio
async def test_get_admin_feedbacks_filter_by_project_id(
    thumbs_down_feedback, shared_project
):
    """project_id filter scopes results to that project."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, project_id=shared_project.id
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id in ids

    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, project_id=uuid.uuid4()
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id not in ids


@pytest.mark.asyncio
async def test_get_admin_feedbacks_filter_by_feedback_type(
    thumbs_down_feedback, db_user, issue, workflow_run
):
    """feedback_type filter returns only matching feedback."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, feedback_type=FeedbackType.THUMBS_DOWN
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id in ids

    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, feedback_type=FeedbackType.THUMBS_UP
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id not in ids


@pytest.mark.asyncio
async def test_get_admin_feedbacks_filter_by_workflow_type(
    thumbs_down_feedback, issue
):
    """workflow_type filter matches feedback for that issue workflow type."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, workflow_type=WorkflowRunType.CITATION_DETECTION
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id in ids

    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session, workflow_type=WorkflowRunType.DOCUMENT_PROCESSING
        )
    ids = [row["feedback"].id for row in rows]
    assert thumbs_down_feedback.id not in ids


@pytest.mark.asyncio
async def test_get_admin_feedbacks_row_structure(thumbs_down_feedback, issue):
    """Each row contains the expected keys."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(session=session)

    assert len(rows) >= 1
    row = next(r for r in rows if r["feedback"].id == thumbs_down_feedback.id)
    assert set(row.keys()) == {"feedback", "issue", "project", "user"}
