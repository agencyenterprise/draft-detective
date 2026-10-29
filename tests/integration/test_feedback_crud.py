"""Feedback writes: the upsert key, the ownership gate and delete.

The upsert finds an existing row by issue_id for issue feedback and by entity_path
(a JSONB equality) for everything else, so these run against Postgres rather than
mocks.
"""

import uuid
from collections.abc import Awaitable, Callable

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue, IssueStatus
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services import feedback_service
from lib.workflows.models import SeverityEnum

CLAIM_PATH = {"chunk_index": 0, "claim_index": 1}


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
        chunk_indices=[0],
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
    """Two issues on the same run. Their feedback rows share entity_path={}, so
    only issue_id tells them apart."""
    first, second = _make_issue(run, "First"), _make_issue(run, "Second")
    await _add(first)
    await _add(second)
    return first, second


async def _upsert(
    run: WorkflowRun,
    user: User,
    feedback_type: FeedbackType,
    entity_path: dict | None = None,
    issue_id: uuid.UUID | None = None,
    feedback_text: str | None = None,
) -> Feedback:
    async with get_async_db_session() as session:
        return await feedback_service.create_or_update_feedback(
            session=session,
            workflow_run_id=run.id,
            entity_path=entity_path if entity_path is not None else {},
            feedback_type=feedback_type,
            user=user,
            feedback_text=feedback_text,
            issue_id=issue_id,
        )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_feedback_is_updated_in_place(run, author, issues):
    issue, _ = issues
    first = await _upsert(
        run,
        author,
        FeedbackType.THUMBS_DOWN,
        issue_id=issue.id,
        feedback_text="wrong page",
    )
    second = await _upsert(run, author, FeedbackType.THUMBS_UP, issue_id=issue.id)

    assert second.id == first.id
    rows = await _feedback_rows(run.id)
    assert len(rows) == 1
    assert rows[0].feedback_type == FeedbackType.THUMBS_UP
    assert rows[0].feedback_text is None


@pytest.mark.asyncio
async def test_each_issue_on_a_run_keeps_its_own_feedback(run, author, issues):
    first_issue, second_issue = issues
    await _upsert(run, author, FeedbackType.THUMBS_UP, issue_id=first_issue.id)
    await _upsert(run, author, FeedbackType.THUMBS_DOWN, issue_id=second_issue.id)

    by_issue = {row.issue_id: row.feedback_type for row in await _feedback_rows(run.id)}
    assert by_issue == {
        first_issue.id: FeedbackType.THUMBS_UP,
        second_issue.id: FeedbackType.THUMBS_DOWN,
    }


@pytest.mark.asyncio
async def test_entity_feedback_matches_the_path_regardless_of_key_order(run, author):
    """JSONB equality ignores key order, so the same claim addressed with its keys
    swapped is still the same row."""
    first = await _upsert(run, author, FeedbackType.THUMBS_DOWN, entity_path=CLAIM_PATH)
    swapped = {"claim_index": 1, "chunk_index": 0}
    second = await _upsert(run, author, FeedbackType.THUMBS_UP, entity_path=swapped)

    assert second.id == first.id
    assert len(await _feedback_rows(run.id)) == 1


@pytest.mark.asyncio
async def test_a_different_entity_path_creates_a_new_row(run, author):
    await _upsert(run, author, FeedbackType.THUMBS_DOWN, entity_path=CLAIM_PATH)
    await _upsert(run, author, FeedbackType.THUMBS_UP, entity_path={"chunk_index": 0})

    paths = [row.entity_path for row in await _feedback_rows(run.id)]
    assert sorted(paths, key=len) == [{"chunk_index": 0}, CLAIM_PATH]

    async with get_async_db_session() as session:
        found = await feedback_service.get_feedback(
            session=session, workflow_run_id=run.id, entity_path=CLAIM_PATH, user=author
        )
    assert found is not None
    assert found.feedback_type == FeedbackType.THUMBS_DOWN


@pytest.mark.asyncio
@pytest.mark.parametrize("rated", [1, 2], ids=["one-rated-issue", "two-rated-issues"])
async def test_run_level_feedback_leaves_issue_feedback_alone(
    rated, run, author, issues
):
    """Issue feedback is stored with entity_path={} too, so run-level feedback must
    not match it. It used to silently overwrite and unlink a single rated issue's
    row, and fail with MultipleResultsFound once two were rated."""
    rated_issues = issues[:rated]
    for issue in rated_issues:
        await _upsert(run, author, FeedbackType.THUMBS_DOWN, issue_id=issue.id)
    created = await _upsert(run, author, FeedbackType.THUMBS_UP)
    updated = await _upsert(run, author, FeedbackType.THUMBS_UP, feedback_text="meh")

    assert updated.id == created.id
    by_issue = {row.issue_id: row.feedback_type for row in await _feedback_rows(run.id)}
    assert by_issue == {
        **{issue.id: FeedbackType.THUMBS_DOWN for issue in rated_issues},
        None: FeedbackType.THUMBS_UP,
    }

    async with get_async_db_session() as session:
        found = await feedback_service.get_feedback(
            session=session, workflow_run_id=run.id, entity_path={}, user=author
        )
    assert found is not None and found.id == created.id


# ---------------------------------------------------------------------------
# Ownership gate
# ---------------------------------------------------------------------------

RunCall = Callable[[AsyncSession, uuid.UUID, User], Awaitable[object]]

RUN_SCOPED_CALLS: dict[str, RunCall] = {
    "create_or_update": lambda session, run_id, user: (
        feedback_service.create_or_update_feedback(
            session=session,
            workflow_run_id=run_id,
            entity_path={},
            feedback_type=FeedbackType.THUMBS_UP,
            user=user,
        )
    ),
    "get_feedback": lambda session, run_id, user: feedback_service.get_feedback(
        session=session, workflow_run_id=run_id, entity_path={}, user=user
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("call", RUN_SCOPED_CALLS.values(), ids=RUN_SCOPED_CALLS.keys())
async def test_a_stranger_is_refused_on_someone_elses_run(call, run, stranger):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await call(session, run.id, stranger)

    assert excinfo.value.status_code == 403
    assert await _feedback_rows(run.id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("call", RUN_SCOPED_CALLS.values(), ids=RUN_SCOPED_CALLS.keys())
async def test_an_unknown_run_is_a_404(call, author):
    with pytest.raises(HTTPException) as excinfo:
        async with get_async_db_session() as session:
            await call(session, uuid.uuid4(), author)

    assert excinfo.value.status_code == 404


# ---------------------------------------------------------------------------
# Feedback by issue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_by_issue_returns_the_authors_row(run, author, issues):
    first_issue, second_issue = issues
    created = await _upsert(
        run, author, FeedbackType.THUMBS_UP, issue_id=first_issue.id
    )

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
async def test_the_author_deletes_their_feedback(run, author):
    created = await _upsert(run, author, FeedbackType.THUMBS_UP, entity_path=CLAIM_PATH)

    async with get_async_db_session() as session:
        deleted = await feedback_service.delete_feedback(
            session=session, feedback_id=created.id, user=author
        )

    assert deleted is True
    assert await _feedback_rows(run.id) == []


@pytest.mark.asyncio
async def test_deleting_someone_elses_feedback_is_refused(run, author, stranger):
    created = await _upsert(run, author, FeedbackType.THUMBS_UP, entity_path=CLAIM_PATH)

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
