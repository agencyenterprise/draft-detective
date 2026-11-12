"""The same-type lock runs queued runs of one type in the order they were created.

Two PENDING runs of one type can be queued at once: a double-click on Run, a
batch start next to a single one, two users on one project. When both are
waiting, the older one must go first; a RUNNING run still holds back every
PENDING one. A run that passes claims the queue (it is RUNNING from then on),
so a run that shows up later, released from a gate or committed after a newer
one, waits for it. These run on real rows because the order comes from the
query.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_runs.gates import claim_run_awaiting_approval
from lib.services.workflow_runs.orchestration import wait_for_dependencies
from lib.services.workflow_runs.queue import claim_same_type_queue_head
from lib.workflows.models import WorkflowRunType

RUN_TYPE = WorkflowRunType.REFERENCE_DOWNLOADER
BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class WouldWait(Exception):
    """Raised in place of the poll sleep: the run is held by the lock."""


class Seeder:
    """Creates a user, a project and its runs, and deletes them afterwards."""

    def __init__(self) -> None:
        self.user_id = uuid.uuid4()
        self.project_id = uuid.uuid4()

    async def setup(self) -> None:
        async with get_async_db_session() as session:
            session.add(
                User(
                    id=self.user_id,
                    email=f"lock-order-{self.user_id}@example.com",
                    name="Lock Order Tester",
                    role=UserRole.USER,
                    show_experimental_features=False,
                )
            )
            await session.commit()
        async with get_async_db_session() as session:
            session.add(
                Project(id=self.project_id, title="Lock order", user_id=self.user_id)
            )
            await session.commit()

    async def run(self, status: WorkflowRunStatus, minutes_ago: int) -> str:
        run_id = uuid.uuid4()
        async with get_async_db_session() as session:
            session.add(
                WorkflowRun(
                    id=run_id,
                    project_id=self.project_id,
                    type=RUN_TYPE,
                    langgraph_thread_id=str(uuid.uuid4()),
                    status=status,
                    revision=1,
                    created_at=BASE_TIME - timedelta(minutes=minutes_ago),
                )
            )
            await session.commit()
        return str(run_id)

    async def status(self, run_id: str) -> WorkflowRunStatus:
        async with get_async_db_session() as session:
            run = await session.get(WorkflowRun, uuid.UUID(run_id))
            assert run is not None
            return run.status

    async def cleanup(self) -> None:
        # workflow_runs go with the project via the FK's ON DELETE CASCADE.
        async with get_async_db_session() as session:
            project = await session.get(Project, self.project_id)
            if project:
                await session.delete(project)
                await session.commit()
            user = await session.get(User, self.user_id)
            if user:
                await session.delete(user)
                await session.commit()


@pytest_asyncio.fixture
async def seeder() -> AsyncIterator[Seeder]:
    s = Seeder()
    await s.setup()
    yield s
    await s.cleanup()


@pytest.fixture(autouse=True)
def lock_only_manifest() -> Iterator[None]:
    """A manifest with no dependencies, so only the same-type lock can block."""
    manifest = MagicMock()
    manifest.independent_runs = False
    manifest.required_dependencies = []
    manifest.optional_dependencies = []
    with (
        patch(
            "lib.services.workflow_runs.orchestration.get_workflow_manifest",
            return_value=manifest,
        ),
        patch(
            "lib.services.workflow_runs.orchestration.asyncio.sleep",
            side_effect=WouldWait,
        ),
    ):
        yield


async def _proceeds(seeder: Seeder, run_id: str) -> bool:
    try:
        await wait_for_dependencies(RUN_TYPE, str(seeder.project_id), run_id)
    except WouldWait:
        return False
    return True


@pytest.mark.asyncio
async def test_older_pending_run_goes_before_a_newer_one(seeder: Seeder) -> None:
    older = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=2)
    newer = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)

    assert await _proceeds(seeder, older)
    assert not await _proceeds(seeder, newer)


@pytest.mark.asyncio
async def test_running_run_holds_back_an_older_pending_one(seeder: Seeder) -> None:
    older = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=2)
    await seeder.run(WorkflowRunStatus.RUNNING, minutes_ago=1)

    assert not await _proceeds(seeder, older)


@pytest.mark.asyncio
async def test_finished_and_awaiting_runs_do_not_hold_back_a_pending_one(
    seeder: Seeder,
) -> None:
    await seeder.run(WorkflowRunStatus.COMPLETED, minutes_ago=4)
    await seeder.run(WorkflowRunStatus.FAILED, minutes_ago=3)
    await seeder.run(WorkflowRunStatus.AWAITING_APPROVAL, minutes_ago=2)
    pending = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)

    assert await _proceeds(seeder, pending)


@pytest.mark.asyncio
async def test_runs_with_the_same_created_at_never_both_go(seeder: Seeder) -> None:
    first = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    second = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)

    assert await _proceeds(seeder, first) != await _proceeds(seeder, second)


@pytest.mark.asyncio
async def test_a_run_that_passes_is_running_from_then_on(seeder: Seeder) -> None:
    pending = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)

    assert await _proceeds(seeder, pending)
    assert await seeder.status(pending) == WorkflowRunStatus.RUNNING


@pytest.mark.asyncio
async def test_an_older_run_released_from_its_gate_waits_for_one_that_passed(
    seeder: Seeder,
) -> None:
    """A newer run passed while the older one awaited approval; releasing the
    older one must not start it alongside the newer one."""
    older = await seeder.run(WorkflowRunStatus.AWAITING_APPROVAL, minutes_ago=2)
    newer = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    assert await _proceeds(seeder, newer)

    assert await claim_run_awaiting_approval(older)

    assert not await _proceeds(seeder, older)


@pytest.mark.asyncio
async def test_an_older_run_committed_late_waits_for_one_that_passed(
    seeder: Seeder,
) -> None:
    """Runs take created_at before they commit, so an older run can become
    visible after a newer one already passed."""
    newer = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    assert await _proceeds(seeder, newer)

    older = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=2)

    assert not await _proceeds(seeder, older)


@pytest.mark.asyncio
async def test_a_crowd_of_queued_runs_lets_exactly_one_through(seeder: Seeder) -> None:
    runs = [
        await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1) for _ in range(8)
    ]

    runs_ahead = await asyncio.gather(*(claim_same_type_queue_head(r) for r in runs))

    assert sum(run_ahead is None for run_ahead in runs_ahead) == 1
    statuses = [await seeder.status(r) for r in runs]
    assert statuses.count(WorkflowRunStatus.RUNNING) == 1
