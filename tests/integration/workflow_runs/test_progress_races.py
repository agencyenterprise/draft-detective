"""Concurrency tests for get_or_create_progress.

Each test pauses one get_or_create_progress call right after its upsert, before
it commits, lets another coroutine act on the same (run, name) entry, then
resumes it.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.workflow_progress import ProgressLevel, WorkflowProgress
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs import progress as progress_service
from lib.services.workflow_runs.progress import (
    get_or_create_progress,
    increment_and_complete_if_done,
)

# Long enough for an unblocked coroutine to finish its DB round trips.
_SETTLE_SECONDS = 1.0


@pytest_asyncio.fixture
async def workflow_run_id() -> AsyncIterator[uuid.UUID]:
    """A fresh project and workflow run, deleted (with its progress) afterwards."""
    project_id, run_id = uuid.uuid4(), uuid.uuid4()
    async with get_async_db_session() as session:
        session.add(Project(id=project_id, title="Progress race test"))
        await session.flush()
        session.add(
            WorkflowRun(
                id=run_id,
                langgraph_thread_id=str(uuid.uuid4()),
                project_id=project_id,
                type=WorkflowRunType.DOCUMENT_PROCESSING,
                status=WorkflowRunStatus.RUNNING,
            )
        )
        await session.commit()

    yield run_id

    async with get_async_db_session() as session:
        project = await session.get(Project, project_id)
        if project:
            await session.delete(project)
            await session.commit()


class _PauseAfterFirstQuery:
    """Makes the next session opened by the progress service stop after its first query."""

    def __init__(self) -> None:
        self.paused = asyncio.Event()
        self.resume = asyncio.Event()
        self._armed = True

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with get_async_db_session() as session:
            if self._armed:
                self._armed = False
                session.execute = self._pausing(session.execute)  # type: ignore[method-assign]
            yield session

    def _pausing(
        self, execute: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        async def pausing_execute(*args: Any, **kwargs: Any) -> Any:
            result = await execute(*args, **kwargs)
            self.paused.set()
            await self.resume.wait()
            return result

        return pausing_execute


async def _entries(workflow_run_id: uuid.UUID) -> list[WorkflowProgress]:
    async with get_async_db_session() as session:
        stmt = select(WorkflowProgress).where(
            col(WorkflowProgress.workflow_run_id) == workflow_run_id
        )
        return list((await session.execute(stmt)).scalars().all())


@pytest.mark.asyncio
async def test_concurrent_creates_share_one_entry(
    workflow_run_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second caller joins an entry the first has created but not yet committed."""
    pause = _PauseAfterFirstQuery()
    monkeypatch.setattr(progress_service, "get_async_db_session", pause.session)
    name = "Parallel node"

    first = asyncio.create_task(
        get_or_create_progress(workflow_run_id, name, ProgressLevel.NODE)
    )
    await pause.paused.wait()  # has inserted the entry, not committed
    second = asyncio.create_task(
        get_or_create_progress(workflow_run_id, name, ProgressLevel.NODE)
    )
    await asyncio.wait({second}, timeout=_SETTLE_SECONDS)
    pause.resume.set()

    assert await first == await second
    [entry] = await _entries(workflow_run_id)
    assert entry.total_steps == 2


@pytest.mark.asyncio
async def test_many_parallel_nodes_batch_into_one_entry(
    workflow_run_id: uuid.UUID,
) -> None:
    ids = await asyncio.gather(
        *(
            get_or_create_progress(workflow_run_id, "Fan-out", ProgressLevel.NODE)
            for _ in range(20)
        )
    )
    assert len(set(ids)) == 1
    [entry] = await _entries(workflow_run_id)
    assert entry.total_steps == 20


@pytest.mark.asyncio
async def test_joining_an_entry_that_completes_meanwhile(
    workflow_run_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A node never joins an entry that another node marks completed under it."""
    name = "Parallel node"
    progress_id = await get_or_create_progress(
        workflow_run_id, name, ProgressLevel.NODE
    )
    pause = _PauseAfterFirstQuery()
    monkeypatch.setattr(progress_service, "get_async_db_session", pause.session)

    joining = asyncio.create_task(
        get_or_create_progress(workflow_run_id, name, ProgressLevel.NODE)
    )
    await pause.paused.wait()  # has joined the entry, not committed
    finishing = asyncio.create_task(increment_and_complete_if_done(progress_id))
    await asyncio.wait({finishing}, timeout=_SETTLE_SECONDS)
    pause.resume.set()

    joined_id = await joining
    await finishing
    joined = next(e for e in await _entries(workflow_run_id) if e.id == joined_id)
    assert joined.completed_at is None
    assert joined.current_step < joined.total_steps
