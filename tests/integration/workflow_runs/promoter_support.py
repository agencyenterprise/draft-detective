"""Fixtures and helpers for the promoter and workflow-job tests.

Each test gets its own project and its own queue name, so the jobs it defers
are never taken by a worker of another test sharing the database.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel
from sqlalchemy import delete, select, text
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.config.task_queue import task_queue
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.start import start_or_join_run
from lib.workflows.registry import get_config_type, get_workflow_manifest

WAIT_SECONDS = 20.0


class Scene(BaseModel):
    """One test's project, its owner and its queue."""

    project_id: str
    user: User
    queue: str


@asynccontextmanager
async def open_scene() -> AsyncIterator[Scene]:
    user = User(
        id=uuid.uuid4(),
        email=f"promoter-{uuid.uuid4()}@example.com",
        name="promoter",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(id=uuid.uuid4(), user_id=user.id, title="promoter")
    for row in (user, project):
        async with get_async_db_session() as session:
            session.add(row)
            await session.commit()
    queue = f"wf-test-{uuid.uuid4().hex[:12]}"
    with patch("lib.config.task_queue.WORKFLOW_QUEUE", queue):
        async with task_queue.open_async():
            yield Scene(project_id=str(project.id), user=user, queue=queue)
    async with get_async_db_session() as session:
        await session.execute(
            text("DELETE FROM procrastinate_jobs WHERE queue_name = :queue"),
            {"queue": queue},
        )
        # Deleting the project cascades to its runs and gate approvals.
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


async def start(scene: Scene, workflow_type: WorkflowRunType, revision: int = 1) -> str:
    """Create (or join) the waiting run, as a start does."""
    config = get_config_type(workflow_type).model_validate(
        {"project_id": scene.project_id, "type": workflow_type}
    )
    begun = await start_or_join_run(
        config, workflow_type, revision, started_by=scene.user.id
    )
    return begun.run_id


async def add_run(
    scene: Scene,
    workflow_type: WorkflowRunType,
    status: WorkflowRunStatus,
    revision: int = 1,
) -> str:
    """A run in any status, written directly."""
    run = WorkflowRun(
        project_id=uuid.UUID(scene.project_id),
        type=workflow_type,
        langgraph_thread_id=str(uuid.uuid4()),
        status=status,
        revision=revision,
        independent_run=get_workflow_manifest(workflow_type).independent_runs,
    )
    async with get_async_db_session() as session:
        session.add(run)
        await session.commit()
    return str(run.id)


async def status_of(run_id: str) -> WorkflowRunStatus:
    async with get_async_db_session() as session:
        stmt = select(col(WorkflowRun.status)).where(col(WorkflowRun.id) == run_id)
        return (await session.execute(stmt)).scalar_one()


class QueuedJob(BaseModel):
    run_id: str
    status: str
    lock: str | None


async def jobs(scene: Scene) -> list[QueuedJob]:
    """The test's workflow jobs, oldest first."""
    async with get_async_db_session() as session:
        rows = await session.execute(
            text(
                "SELECT args->>'workflow_run_id', status, lock FROM procrastinate_jobs "
                "WHERE queue_name = :queue ORDER BY id"
            ),
            {"queue": scene.queue},
        )
        return [QueuedJob(run_id=r[0], status=r[1], lock=r[2]) for r in rows]


async def queued_run_ids(scene: Scene) -> list[str]:
    return [job.run_id for job in await jobs(scene) if job.status == "todo"]


async def wait_until(check: Callable[[], Awaitable[Any]]) -> None:
    async with asyncio.timeout(WAIT_SECONDS):
        while not await check():
            await asyncio.sleep(0.1)
