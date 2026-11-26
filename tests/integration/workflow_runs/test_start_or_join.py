"""A start creates the waiting run of its type, or joins the one that exists.

Runs against the real database: the unique indexes are what keep a type to
one RUNNING and one waiting run, so mocks could not show it.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col

from lib.api.services.workflow_runner import start_workflow_run
from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.encryption import decrypt_value
from lib.services.review_assistant_requests import record_request
from lib.services.workflow_runs.service import (
    get_workflow_run,
    persist_workflow_run_state,
)
from lib.services.workflow_runs.start import RunStart, start_or_join_run
from lib.workflows.registry import get_config_type
from lib.workflows.review_assistant.state import (
    ReviewAssistantConfig,
    ReviewAssistantState,
)

ABBREVIATIONS = WorkflowRunType.ABBREVIATION_SCAN_V2
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


@pytest_asyncio.fixture
async def user_id(project_id: str) -> uuid.UUID:
    """The owner of the test's project."""
    async with get_async_db_session() as session:
        project = await session.get(Project, uuid.UUID(project_id))
    assert project is not None
    return project.user_id


async def _start(
    project_id: str,
    workflow_type: WorkflowRunType = ABBREVIATIONS,
    *,
    revision: int = 1,
    model: str | None = None,
    started_by: uuid.UUID | None = None,
    api_key: str | None = None,
) -> RunStart:
    config = get_config_type(workflow_type).model_validate(
        {
            "project_id": project_id,
            "type": workflow_type,
            "model": model,
            "openai_api_key": api_key,
        }
    )
    return await start_or_join_run(
        config, workflow_type, revision, started_by=started_by
    )


async def _set_status(run_id: str, status: WorkflowRunStatus) -> None:
    async with get_async_db_session() as session:
        await session.execute(
            update(WorkflowRun)
            .where(col(WorkflowRun.id) == run_id)
            .values(status=status)
        )
        await session.commit()


async def _run(run_id: str) -> WorkflowRun:
    async with get_async_db_session() as session:
        run = await session.get(WorkflowRun, uuid.UUID(run_id))
    assert run is not None
    return run


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

    assert second.created
    assert third.run_id == second.run_id and not third.created
    # The joined run keeps the model its row records.
    assert (await _run(third.run_id)).model == "openai:gpt-5.6-sol"
    assert await _statuses(project_id, ABBREVIATIONS) == [
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.PENDING,
    ]


@pytest.mark.asyncio
async def test_a_run_stores_its_config_its_starter_and_its_key_encrypted_apart(
    project_id, user_id
):
    start = await _start(
        project_id, model="openai:gpt-5.6-sol", started_by=user_id, api_key="sk-secret"
    )

    run = await _run(start.run_id)
    assert run.started_by_user_id == user_id
    assert run.config_json is not None
    assert run.config_json["project_id"] == project_id
    assert run.config_json["model"] == "openai:gpt-5.6-sol"
    assert "openai_api_key" not in run.config_json
    assert "sk-secret" not in str(run.config_json)
    # The request's key is kept apart, encrypted, for the job to take.
    assert run.encrypted_openai_api_key is not None
    assert "sk-secret" not in run.encrypted_openai_api_key
    assert decrypt_value(run.encrypted_openai_api_key) == "sk-secret"


@pytest.mark.asyncio
async def test_concurrent_starts_create_one_run(project_id):
    starts = await asyncio.gather(*(_start(project_id) for _ in range(8)))

    assert len({start.run_id for start in starts}) == 1
    assert sum(start.created for start in starts) == 1
    assert await _statuses(project_id, ABBREVIATIONS) == [WorkflowRunStatus.PENDING]


@pytest.mark.asyncio
async def test_independent_runs_get_a_new_row_each(project_id):
    starts = [await _start(project_id, REVIEW_ASSISTANT) for _ in range(3)]
    await _set_status(starts[0].run_id, WorkflowRunStatus.RUNNING)
    starts.append(await _start(project_id, REVIEW_ASSISTANT))

    assert len({start.run_id for start in starts}) == 4
    assert all(start.created for start in starts)


@pytest.mark.asyncio
async def test_a_cancelled_waiting_run_is_not_joined(project_id):
    cancelled = await _start(project_id)
    await _set_status(cancelled.run_id, WorkflowRunStatus.CANCELLED)

    fresh = await _start(project_id)

    assert fresh.run_id != cancelled.run_id and fresh.created


@pytest.mark.asyncio
async def test_a_start_joins_a_run_parked_behind_a_gate(project_id):
    parked = await _start(project_id)
    await _set_status(parked.run_id, WorkflowRunStatus.AWAITING_APPROVAL)

    again = await _start(project_id)

    assert again.run_id == parked.run_id and not again.created
    assert again.status == WorkflowRunStatus.AWAITING_APPROVAL


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
async def test_start_workflow_run_queues_one_behind_a_running_run(project_id, user_id):
    """Through the API's start path: the second start creates the waiting run,
    the third joins it, and each start ends with a promoter pass."""
    project = Project(id=uuid.UUID(project_id), user_id=user_id, title="t")
    config = get_config_type(ABBREVIATIONS)(project_id=project_id)
    user = User(id=user_id, email="u@example.com", name="u")
    with (
        patch(
            "lib.api.services.workflow_runner.authorized_project",
            new=AsyncMock(return_value=project),
        ),
        patch("lib.api.services.workflow_runner.assert_api_key_available"),
        patch(
            "lib.api.services.workflow_runner.promote_ready_runs", new=AsyncMock()
        ) as promote,
    ):
        first = await start_workflow_run(config, user)
        await _set_status(first, WorkflowRunStatus.RUNNING)
        second = await start_workflow_run(config, user)
        third = await start_workflow_run(config, user)

    assert len({first, second}) == 2 and third == second
    assert promote.await_count == 3
    promote.assert_awaited_with(project_id, 1)


@pytest.mark.asyncio
async def test_a_request_recorded_after_its_job_started_leaves_the_jobs_state(
    project_id,
):
    """The Review Assistant records its request once its run exists, and a job
    on another worker may have started (and written state) by then."""
    start = await _start(project_id, REVIEW_ASSISTANT)
    config = ReviewAssistantConfig(project_id=project_id)
    await persist_workflow_run_state(
        start.run_id, ReviewAssistantState(config=config, guard_message="ran first")
    )

    await record_request(start.run_id, config)

    run = await _run_with_state(start.run_id)
    assert run.state_json is not None
    assert run.state_json["guard_message"] == "ran first"


@pytest.mark.asyncio
async def test_a_request_is_recorded_on_a_run_with_no_state_yet(project_id):
    start = await _start(project_id, REVIEW_ASSISTANT)

    await record_request(start.run_id, ReviewAssistantConfig(project_id=project_id))

    run = await _run_with_state(start.run_id)
    assert run.state_json is not None
    assert run.state_json["config"]["project_id"] == project_id


async def _run_with_state(run_id: str) -> WorkflowRun:
    return await get_workflow_run(run_id, include_state=True)
