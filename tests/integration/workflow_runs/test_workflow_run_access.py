"""Who `get_accessible_workflow_run` hands a run to.

A run is reached through its project's gate: the owner gets it at any level, an
admin on a full_project share only at READ. A run with no project has no owner, so
it is refused like a run that does not exist. Internal callers use
`get_workflow_run`, which returns every run, project or not.
"""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException

from lib.api.routers.workflows import cancel_workflow_run_endpoint
from lib.config.database import get_async_db_session
from lib.models.project import AccessLevel, FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.access import get_accessible_workflow_run
from lib.services.workflow_runs.service import get_workflow_run


async def _add(record: object) -> None:
    async with get_async_db_session() as session:
        session.add(record)
        await session.commit()


async def _delete(model: type, record_id: uuid.UUID) -> None:
    async with get_async_db_session() as session:
        existing = await session.get(model, record_id)
        if existing:
            await session.delete(existing)
            await session.commit()


async def _make_user(role: UserRole = UserRole.USER) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4()}@example.com",
        name="Test User",
        role=role,
        show_experimental_features=False,
    )
    await _add(user)
    return user


def _run(project_id: uuid.UUID | None) -> WorkflowRun:
    return WorkflowRun(
        id=uuid.uuid4(),
        project_id=project_id,
        type=WorkflowRunType.RECOMMENDATION_CHECK,
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.RUNNING,
    )


@pytest_asyncio.fixture
async def owner() -> AsyncIterator[User]:
    user = await _make_user()
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def stranger() -> AsyncIterator[User]:
    user = await _make_user()
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def admin() -> AsyncIterator[User]:
    user = await _make_user(UserRole.ADMIN)
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def owned_run(owner: User) -> AsyncIterator[WorkflowRun]:
    """A run on a project shared as full_project, so an admin may read it."""
    project = Project(
        id=uuid.uuid4(),
        title="Owned Project",
        user_id=owner.id,
        feedback_visibility=FeedbackVisibility.FULL_PROJECT,
    )
    await _add(project)
    run = _run(project.id)
    await _add(run)
    yield run
    await _delete(WorkflowRun, run.id)
    await _delete(Project, project.id)


@pytest_asyncio.fixture
async def projectless_run() -> AsyncIterator[WorkflowRun]:
    run = _run(None)
    await _add(run)
    yield run
    await _delete(WorkflowRun, run.id)


@pytest.mark.asyncio
async def test_owner_gets_their_run(owner: User, owned_run: WorkflowRun) -> None:
    run = await get_accessible_workflow_run(
        str(owned_run.id), owner, required_level=AccessLevel.WRITE
    )
    assert run.id == owned_run.id


@pytest.mark.asyncio
async def test_stranger_is_refused_someone_elses_run(
    stranger: User, owned_run: WorkflowRun
) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_accessible_workflow_run(str(owned_run.id), stranger)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_user_is_refused_a_run_without_a_project(
    stranger: User, projectless_run: WorkflowRun
) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_accessible_workflow_run(str(projectless_run.id), stranger)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_internal_caller_still_gets_a_run_without_a_project(
    projectless_run: WorkflowRun,
) -> None:
    run = await get_workflow_run(str(projectless_run.id))
    assert run.id == projectless_run.id


@pytest.mark.asyncio
async def test_cancel_endpoint_refuses_a_run_without_a_project(
    stranger: User, projectless_run: WorkflowRun
) -> None:
    """The route authorizes through the helper, so the check above guards it."""
    with patch("lib.api.routers.workflows.cancel_run", new=AsyncMock()) as cancel:
        with pytest.raises(HTTPException) as exc:
            await cancel_workflow_run_endpoint(
                str(projectless_run.id), current_user=stranger
            )
    assert exc.value.status_code == 404
    cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_reads_a_shared_run_but_cannot_write_it(
    admin: User, owned_run: WorkflowRun
) -> None:
    run = await get_accessible_workflow_run(str(owned_run.id), admin)
    assert run.id == owned_run.id
    with pytest.raises(HTTPException) as exc:
        await get_accessible_workflow_run(
            str(owned_run.id), admin, required_level=AccessLevel.WRITE
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_cancel_endpoint_refuses_an_admin_on_a_shared_project(
    admin: User, owned_run: WorkflowRun
) -> None:
    """Cancelling is the owner's call: reading a shared project is not enough."""
    with patch("lib.api.routers.workflows.cancel_run", new=AsyncMock()) as cancel:
        with pytest.raises(HTTPException) as exc:
            await cancel_workflow_run_endpoint(str(owned_run.id), current_user=admin)
    assert exc.value.status_code == 403
    cancel.assert_not_awaited()
