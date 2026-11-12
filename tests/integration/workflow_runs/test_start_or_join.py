"""A start creates the waiting run of its type, or joins the one that exists.

Runs against the real database: the unique indexes are what keep a type to
one RUNNING and one waiting run, so mocks could not show it.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col

from lib.api.services.workflow_runner import start_workflow_run
from lib.config.database import get_async_db_session
from lib.models.project import AccessLevel, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.workflow_runs.gates import (
    approve_gate,
    release_runs_awaiting_approval,
)
from lib.services.workflow_runs.start import start_or_join_run
from lib.workflows.models import WorkflowGate
from lib.workflows.registry import get_config_type

ABBREVIATIONS = WorkflowRunType.ABBREVIATION_SCAN_V2
CLAIM = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
REVIEW_ASSISTANT = WorkflowRunType.REVIEW_ASSISTANT


@pytest_asyncio.fixture
async def project_id() -> AsyncIterator[str]:
    user = User(
        id=uuid.uuid4(),
        email=f"start-or-join-{uuid.uuid4()}@example.com",
        name="start or join",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(id=uuid.uuid4(), user_id=user.id, title="start or join")
    for row in (user, project):
        async with get_async_db_session() as session:
            session.add(row)
            await session.commit()

    yield str(project.id)

    async with get_async_db_session() as session:
        # Deleting the project cascades to its runs and gate approvals.
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


async def _start(
    project_id: str,
    workflow_type: WorkflowRunType = ABBREVIATIONS,
    *,
    revision: int = 1,
    gated: bool = False,
    model: str | None = None,
):
    return await start_or_join_run(
        project_id, workflow_type, revision, model=model, gated=gated
    )


async def _set_status(run_id: str, status: WorkflowRunStatus) -> None:
    async with get_async_db_session() as session:
        await session.execute(
            update(WorkflowRun)
            .where(col(WorkflowRun.id) == run_id)
            .values(status=status)
        )
        await session.commit()


async def _statuses(
    project_id: str, workflow_type: WorkflowRunType, revision: int = 1
) -> list[WorkflowRunStatus]:
    async with get_async_db_session() as session:
        stmt = (
            select(col(WorkflowRun.status))
            .where(
                col(WorkflowRun.project_id) == project_id,
                col(WorkflowRun.type) == workflow_type,
                col(WorkflowRun.revision) == revision,
            )
            .order_by(col(WorkflowRun.created_at))
        )
        return list((await session.execute(stmt)).scalars().all())


@pytest.mark.asyncio
async def test_a_start_while_one_runs_queues_one_and_a_third_joins_it(project_id):
    first = await _start(project_id)
    await _set_status(first.run_id, WorkflowRunStatus.RUNNING)

    second = await _start(project_id, model="openai:gpt-5.6-sol")
    third = await _start(project_id, model="openai:gpt-5.6-luna")

    assert second.created and second.schedule
    assert third.run_id == second.run_id
    assert not third.created and not third.schedule
    # The joined run keeps the model its row records.
    assert third.model == "openai:gpt-5.6-sol"
    assert await _statuses(project_id, ABBREVIATIONS) == [
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.PENDING,
    ]


@pytest.mark.asyncio
async def test_concurrent_starts_create_one_run_and_schedule_it_once(project_id):
    starts = await asyncio.gather(*(_start(project_id) for _ in range(8)))

    assert len({start.run_id for start in starts}) == 1
    assert sum(start.schedule for start in starts) == 1
    assert await _statuses(project_id, ABBREVIATIONS) == [WorkflowRunStatus.PENDING]


@pytest.mark.asyncio
async def test_independent_runs_get_a_new_row_each(project_id):
    starts = [await _start(project_id, REVIEW_ASSISTANT) for _ in range(3)]
    await _set_status(starts[0].run_id, WorkflowRunStatus.RUNNING)
    starts.append(await _start(project_id, REVIEW_ASSISTANT))

    assert len({start.run_id for start in starts}) == 4
    assert all(start.created and start.schedule for start in starts)


@pytest.mark.asyncio
async def test_a_cancelled_waiting_run_is_not_joined(project_id):
    cancelled = await _start(project_id)
    await _set_status(cancelled.run_id, WorkflowRunStatus.CANCELLED)

    fresh = await _start(project_id)

    assert fresh.run_id != cancelled.run_id
    assert fresh.created and fresh.schedule


@pytest.mark.asyncio
async def test_the_database_refuses_a_second_waiting_run(project_id):
    await _start(project_id)

    with pytest.raises(IntegrityError):
        async with get_async_db_session() as session:
            session.add(
                WorkflowRun(
                    project_id=uuid.UUID(project_id),
                    type=ABBREVIATIONS,
                    status=WorkflowRunStatus.AWAITING_APPROVAL,
                    langgraph_thread_id=str(uuid.uuid4()),
                    revision=1,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_a_gated_start_parks_and_later_starts_join_the_parked_run(project_id):
    parked = await _start(project_id, CLAIM, gated=True, model="openai:gpt-5.6-sol")
    again = await _start(project_id, CLAIM, gated=True)

    assert parked.status == WorkflowRunStatus.AWAITING_APPROVAL
    assert not parked.schedule
    assert again.run_id == parked.run_id and not again.schedule

    # The gate was approved but nothing released the run: an ungated start
    # releases it and schedules it, on the model its row records.
    await approve_gate(project_id, 1, WorkflowGate.REFERENCE_REVIEW)
    released = await _start(project_id, CLAIM, model="openai:gpt-5.6-luna")
    after = await _start(project_id, CLAIM)

    assert released.run_id == parked.run_id
    assert released.status == WorkflowRunStatus.PENDING and released.schedule
    assert released.model == "openai:gpt-5.6-sol"
    assert after.run_id == parked.run_id and not after.schedule


@pytest.mark.asyncio
@pytest.mark.parametrize("revision", range(1, 7))
async def test_a_start_racing_a_gate_approval_schedules_the_run_once(
    project_id, revision
):
    """Starts that read the gate as unapproved (gated) and as approved race the
    approval and its release: one waiting run, scheduled exactly once."""

    async def approve_and_release():
        await approve_gate(project_id, revision, WorkflowGate.REFERENCE_REVIEW)
        return await release_runs_awaiting_approval(project_id, revision)

    results = await asyncio.gather(
        _start(project_id, CLAIM, revision=revision, gated=True),
        approve_and_release(),
        _start(project_id, CLAIM, revision=revision, gated=True),
        _start(project_id, CLAIM, revision=revision),
    )
    starts = [results[0], results[2], results[3]]
    released = results[1]

    assert await _statuses(project_id, CLAIM, revision) == [WorkflowRunStatus.PENDING]
    assert len({start.run_id for start in starts}) == 1
    assert sum(start.schedule for start in starts) + len(released) == 1


@pytest.mark.asyncio
async def test_one_running_run_per_type(project_id):
    first = await _start(project_id)
    await _set_status(first.run_id, WorkflowRunStatus.RUNNING)
    second = await _start(project_id)

    with pytest.raises(IntegrityError):
        await _set_status(second.run_id, WorkflowRunStatus.RUNNING)

    async with get_async_db_session() as session:
        running = await session.scalar(
            select(func.count()).where(
                col(WorkflowRun.project_id) == project_id,
                col(WorkflowRun.status) == WorkflowRunStatus.RUNNING,
            )
        )
    assert running == 1


@pytest.mark.asyncio
async def test_start_workflow_run_queues_one_behind_a_running_run(project_id):
    """Through the API's start path: the second start queues a run and
    schedules it; the third joins it and schedules nothing."""
    project = MagicMock(id=uuid.UUID(project_id), current_revision=1)
    config = get_config_type(ABBREVIATIONS)(project_id=project_id)
    background_tasks = BackgroundTasks()
    with (
        patch(
            "lib.api.services.workflow_runner.get_project_access",
            new=AsyncMock(return_value=(project, AccessLevel.WRITE)),
        ),
        patch(
            "lib.api.services.workflow_runner.assert_project_has_main_file",
            new=AsyncMock(),
        ),
        patch("lib.api.services.workflow_runner._assert_api_key_available"),
    ):
        user = MagicMock()
        first = await start_workflow_run(config, user, background_tasks)
        await _set_status(first, WorkflowRunStatus.RUNNING)
        second = await start_workflow_run(config, user, background_tasks)
        third = await start_workflow_run(config, user, background_tasks)

    assert third == second != first
    assert [task.kwargs["workflow_run_id"] for task in background_tasks.tasks] == [
        first,
        second,
    ]
    assert await _statuses(project_id, ABBREVIATIONS) == [
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.PENDING,
    ]
