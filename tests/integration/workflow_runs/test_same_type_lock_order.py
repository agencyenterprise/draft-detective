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
from sqlalchemy import func, select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_runs import queue as queue_module
from lib.services.workflow_runs.gates import claim_run_awaiting_approval
from lib.services.workflow_runs.orchestration import (
    DEPENDENCY_CHECK_INTERVAL,
    wait_for_dependencies,
)
from lib.services.workflow_runs.queue import (
    claim_same_type_queue_head,
    heartbeat_while_preparing,
    queue_lock_key,
)
from lib.services.workflow_runs.reaper import _find_stuck_runs
from lib.workflows.models import WorkflowCancelledError, WorkflowRunType

RUN_TYPE = WorkflowRunType.REFERENCE_DOWNLOADER
BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class WouldWait(Exception):
    """Raised in place of the poll sleep: the run is held by the lock."""


_real_sleep = asyncio.sleep


async def _poll_sleep_would_wait(delay: float) -> None:
    """asyncio.sleep is one object everywhere, so only the poll's sleep raises."""
    if delay == DEPENDENCY_CHECK_INTERVAL:
        raise WouldWait
    await _real_sleep(delay)


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

    async def run(
        self,
        status: WorkflowRunStatus,
        minutes_ago: int,
        *,
        run_type: WorkflowRunType = RUN_TYPE,
        revision: int = 1,
    ) -> str:
        run_id = uuid.uuid4()
        async with get_async_db_session() as session:
            session.add(
                WorkflowRun(
                    id=run_id,
                    project_id=self.project_id,
                    type=run_type,
                    langgraph_thread_id=str(uuid.uuid4()),
                    status=status,
                    revision=revision,
                    created_at=BASE_TIME - timedelta(minutes=minutes_ago),
                )
            )
            await session.commit()
        return str(run_id)

    async def set(self, run_id: str, **values: object) -> None:
        async with get_async_db_session() as session:
            await session.execute(
                update(WorkflowRun)
                .where(col(WorkflowRun.id) == run_id)
                .values(**values)
            )
            await session.commit()

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
            side_effect=_poll_sleep_would_wait,
        ),
        patch.object(queue_module, "SETUP_HEARTBEAT_INTERVAL", 0.05),
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


@pytest.mark.asyncio
async def test_runs_of_other_types_and_revisions_do_not_hold_a_run_back(
    seeder: Seeder,
) -> None:
    await seeder.run(
        WorkflowRunStatus.RUNNING,
        minutes_ago=3,
        run_type=WorkflowRunType.DOCUMENT_PROCESSING,
    )
    await seeder.run(WorkflowRunStatus.RUNNING, minutes_ago=2, revision=2)
    pending = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)

    assert await _proceeds(seeder, pending)


@pytest.mark.asyncio
async def test_claiming_a_deleted_run_stops_it(seeder: Seeder) -> None:
    with pytest.raises(WorkflowCancelledError):
        await claim_same_type_queue_head(str(uuid.uuid4()))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ended_as", [WorkflowRunStatus.CANCELLED, WorkflowRunStatus.FAILED]
)
async def test_a_run_that_ends_while_blocked_on_the_queue_lock_is_not_admitted(
    seeder: Seeder, ended_as: WorkflowRunStatus
) -> None:
    run = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    key = queue_lock_key(seeder.project_id, RUN_TYPE, 1)
    async with get_async_db_session() as holder:
        await holder.execute(select(func.pg_advisory_lock(key)))
        claim = asyncio.create_task(claim_same_type_queue_head(run))
        await asyncio.sleep(0.5)  # the claim has read its position and waits
        await seeder.set(run, status=ended_as)
        await holder.execute(select(func.pg_advisory_unlock(key)))
        await holder.commit()

    with pytest.raises(WorkflowCancelledError):
        await claim
    assert await seeder.status(run) == ended_as


@pytest.mark.asyncio
async def test_a_run_committed_during_a_claim_waits_for_the_claimer(
    seeder: Seeder,
) -> None:
    """Contention across the read/write boundary: the newer run's claim reads
    before the older run exists and writes after the older run's claim began.
    Only the advisory lock makes the older claim see the newer one RUNNING."""
    newer = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    slow_read = select(func.pg_sleep(1.0)).scalar_subquery().is_not(None)
    real_run_ahead = queue_module._run_ahead
    with patch.object(
        queue_module,
        "_run_ahead",
        side_effect=lambda own: real_run_ahead(own).where(slow_read),
    ):
        newer_claim = asyncio.create_task(claim_same_type_queue_head(newer))
        await asyncio.sleep(0.3)
        older = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=2)
        older_claim = asyncio.create_task(claim_same_type_queue_head(older))
        runs_ahead = await asyncio.gather(newer_claim, older_claim)

    assert runs_ahead[0] is None
    assert runs_ahead[1] is not None
    assert await seeder.status(older) == WorkflowRunStatus.PENDING


@pytest.mark.asyncio
async def test_a_claimed_run_preparing_slowly_is_not_reaped(seeder: Seeder) -> None:
    run = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    assert await _proceeds(seeder, run)
    # A setup that has run for over a minute since the claim.
    await seeder.set(run, started_at=datetime.utcnow() - timedelta(seconds=61))

    async with heartbeat_while_preparing(run):
        await asyncio.sleep(0.2)
        stuck = await _find_stuck_runs(60, 7200)

    assert uuid.UUID(run) not in {r.id for r in stuck}


@pytest.mark.asyncio
async def test_a_run_cancelled_during_setup_stops_before_its_graph(
    seeder: Seeder,
) -> None:
    run = await seeder.run(WorkflowRunStatus.PENDING, minutes_ago=1)
    assert await _proceeds(seeder, run)

    with pytest.raises(WorkflowCancelledError):
        async with heartbeat_while_preparing(run):
            await seeder.set(run, status=WorkflowRunStatus.CANCELLED)
