"""Fixtures shared by the workflow-run integration tests."""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest_asyncio
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from tests.integration.workflow_runs.promoter_support import Scene, open_scene


@pytest_asyncio.fixture
async def stale_run() -> AsyncIterator[tuple[str, str]]:
    """A RUNNING downloader run whose heartbeat is already past any grace."""
    user = User(
        id=uuid.uuid4(),
        email=f"reaped-run-{uuid.uuid4()}@example.com",
        name="reaped",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(id=uuid.uuid4(), user_id=user.id, title="reaped run")
    long_ago = datetime.utcnow() - timedelta(hours=1)
    run = WorkflowRun(
        id=uuid.uuid4(),
        langgraph_thread_id=str(uuid.uuid4()),
        project_id=project.id,
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        status=WorkflowRunStatus.RUNNING,
        started_at=long_ago,
        heartbeat_at=long_ago,
    )
    for row in (user, project, run):
        async with get_async_db_session() as session:
            session.add(row)
            await session.commit()

    yield str(run.id), str(project.id)

    async with get_async_db_session() as session:
        # Deleting the project cascades to its runs.
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


@pytest_asyncio.fixture
async def scene() -> AsyncIterator[Scene]:
    """A project of its own and a queue name of its own (see promoter_support)."""
    async with open_scene() as opened:
        yield opened
