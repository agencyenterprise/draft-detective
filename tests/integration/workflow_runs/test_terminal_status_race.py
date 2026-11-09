"""A terminal status must survive a status write that raced it.

update_workflow_run_status skips rows that already hold a terminal status.
That guard has to hold when the other writer has not committed yet either:
the runner's COMPLETED arriving while the reaper's FAILED is in flight must
not overwrite it.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs.service import update_workflow_run_status


@pytest_asyncio.fixture
async def running_run_id():
    run_id = uuid.uuid4()
    async with get_async_db_session() as session:
        session.add(
            WorkflowRun(
                id=run_id,
                langgraph_thread_id=str(uuid.uuid4()),
                project_id=None,
                type=WorkflowRunType.DOCUMENT_PROCESSING,
                status=WorkflowRunStatus.RUNNING,
            )
        )
        await session.commit()

    yield str(run_id)

    async with get_async_db_session() as session:
        run = await session.get(WorkflowRun, run_id)
        if run:
            await session.delete(run)
            await session.commit()


async def _wait_until_blocked_by(pid: int) -> None:
    """Wait until some other backend is waiting on a lock `pid` holds."""
    query = text(
        "SELECT count(*) FROM pg_stat_activity WHERE :pid = ANY(pg_blocking_pids(pid))"
    )
    for _ in range(200):
        async with get_async_db_session() as session:
            if (await session.execute(query, {"pid": pid})).scalar_one():
                return
        await asyncio.sleep(0.025)
    raise AssertionError("the concurrent status write never reached the row")


@pytest.mark.asyncio
async def test_a_status_write_racing_an_uncommitted_terminal_one_does_not_overwrite_it(
    running_run_id: str,
):
    async with get_async_db_session() as reaper:
        # The reaper marks the run FAILED but has not committed yet.
        pid = (await reaper.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        await reaper.execute(
            update(WorkflowRun)
            .where(col(WorkflowRun.id) == running_run_id)
            .values(
                status=WorkflowRunStatus.FAILED,
                failure_reason=WorkflowRunFailureReason.NO_HEARTBEAT,
            )
        )
        # Meanwhile the runner finishes and writes COMPLETED.
        runner_write = asyncio.create_task(
            update_workflow_run_status(running_run_id, WorkflowRunStatus.COMPLETED)
        )
        await _wait_until_blocked_by(pid)
        await reaper.commit()

    await runner_write

    async with get_async_db_session() as session:
        run = (
            await session.execute(
                select(WorkflowRun).where(col(WorkflowRun.id) == running_run_id)
            )
        ).scalar_one()
    assert run.status == WorkflowRunStatus.FAILED
    assert run.failure_reason == WorkflowRunFailureReason.NO_HEARTBEAT
