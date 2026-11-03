"""Who `get_workflow_run` hands a run to when it is asked on a user's behalf.

With a user, only the owner of the run's project gets it. A run with no project has
no owner, so it is refused like a run that does not exist. Without a user (internal
callers), every run is returned, project or not.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
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


def _run(project_id: uuid.UUID | None) -> WorkflowRun:
    return WorkflowRun(
        id=uuid.uuid4(),
        project_id=project_id,
        type=WorkflowRunType.RECOMMENDATION_CHECK,
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.RUNNING,
    )


@pytest_asyncio.fixture
async def owner():
    user = await _make_user()
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def stranger():
    user = await _make_user()
    yield user
    await _delete(User, user.id)


@pytest_asyncio.fixture
async def owned_run(owner):
    project = Project(id=uuid.uuid4(), title="Owned Project", user_id=owner.id)
    await _add(project)
    run = _run(project.id)
    await _add(run)
    yield run
    await _delete(WorkflowRun, run.id)
    await _delete(Project, project.id)


@pytest_asyncio.fixture
async def projectless_run():
    run = _run(None)
    await _add(run)
    yield run
    await _delete(WorkflowRun, run.id)


@pytest.mark.asyncio
async def test_owner_gets_their_run(owner, owned_run):
    run = await get_workflow_run(str(owned_run.id), user=owner)
    assert run.id == owned_run.id


@pytest.mark.asyncio
async def test_stranger_is_refused_someone_elses_run(stranger, owned_run):
    with pytest.raises(HTTPException) as exc:
        await get_workflow_run(str(owned_run.id), user=stranger)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_user_is_refused_a_run_without_a_project(stranger, projectless_run):
    with pytest.raises(HTTPException) as exc:
        await get_workflow_run(str(projectless_run.id), user=stranger)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_internal_caller_still_gets_a_run_without_a_project(projectless_run):
    run = await get_workflow_run(str(projectless_run.id))
    assert run.id == projectless_run.id
