"""Integration tests for the reaper's stuck-run SQL predicate.

The unit tests in tests/unit/services/test_workflow_reaper.py stub
`_find_stuck_runs` out, so they don't catch a regression in the SQL itself.
A subtle change like swapping ``or_`` for ``and_``, or comparing
``started_at`` against the wrong cutoff, could silently mass-fail healthy
runs (or, worse, never reap stuck ones) without breaking any existing test.

These tests seed real Postgres rows with controlled timestamps and assert
the predicate selects exactly the right set.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_reaper import _find_stuck_runs


RUNNING_GRACE = 60.0
PENDING_GRACE = 7200.0


async def _insert_run(
    *,
    status: WorkflowRunStatus,
    created_at: datetime,
    started_at: Optional[datetime] = None,
    heartbeat_at: Optional[datetime] = None,
) -> uuid.UUID:
    run_id = uuid.uuid4()
    async with get_async_db_session() as session:
        run = WorkflowRun(
            id=run_id,
            langgraph_thread_id=str(uuid.uuid4()),
            project_id=None,
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            status=status,
            created_at=created_at,
            started_at=started_at,
            heartbeat_at=heartbeat_at,
        )
        session.add(run)
        await session.commit()
    return run_id


@pytest_asyncio.fixture
async def cleanup_runs():
    """Track inserted run IDs and delete them after the test."""
    inserted: list[uuid.UUID] = []
    yield inserted
    if inserted:
        async with get_async_db_session() as session:
            stmt = select(WorkflowRun).where(col(WorkflowRun.id).in_(inserted))
            for run in (await session.execute(stmt)).scalars().all():
                await session.delete(run)
            await session.commit()


# ---------------------------------------------------------------------------
# RUNNING + heartbeat_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_running_with_stale_heartbeat_is_stuck(cleanup_runs):
    """RUNNING + heartbeat_at older than the grace window is reaped."""
    now = datetime.utcnow()
    stuck_id = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(hours=1),
        started_at=now - timedelta(hours=1),
        heartbeat_at=now - timedelta(seconds=RUNNING_GRACE * 2),
    )
    cleanup_runs.append(stuck_id)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    assert stuck_id in stuck_ids


@pytest.mark.asyncio
async def test_running_with_fresh_heartbeat_not_stuck(cleanup_runs):
    """RUNNING + recent heartbeat is alive — not reaped."""
    now = datetime.utcnow()
    fresh_id = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(hours=1),
        started_at=now - timedelta(hours=1),
        heartbeat_at=now - timedelta(seconds=5),  # well within grace
    )
    cleanup_runs.append(fresh_id)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    assert fresh_id not in stuck_ids


# ---------------------------------------------------------------------------
# RUNNING with heartbeat_at NULL — falls back to started_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_running_with_null_heartbeat_and_stale_started_at_is_stuck(cleanup_runs):
    """No heartbeat ever ticked AND started_at is past the grace window → reap."""
    now = datetime.utcnow()
    stuck_id = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(hours=1),
        started_at=now - timedelta(seconds=RUNNING_GRACE * 2),
        heartbeat_at=None,
    )
    cleanup_runs.append(stuck_id)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    assert stuck_id in stuck_ids


@pytest.mark.asyncio
async def test_running_with_null_heartbeat_and_fresh_started_at_not_stuck(cleanup_runs):
    """A run that just started but hasn't ticked yet is given the grace window."""
    now = datetime.utcnow()
    fresh_id = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(seconds=10),
        started_at=now - timedelta(seconds=10),
        heartbeat_at=None,
    )
    cleanup_runs.append(fresh_id)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    assert fresh_id not in stuck_ids


# ---------------------------------------------------------------------------
# PENDING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_older_than_pending_grace_is_stuck(cleanup_runs):
    """PENDING + created_at past the pending grace window → reap."""
    now = datetime.utcnow()
    stuck_id = await _insert_run(
        status=WorkflowRunStatus.PENDING,
        created_at=now - timedelta(seconds=PENDING_GRACE * 2),
    )
    cleanup_runs.append(stuck_id)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    assert stuck_id in stuck_ids


@pytest.mark.asyncio
async def test_pending_within_pending_grace_not_stuck(cleanup_runs):
    """PENDING + created_at within grace → still considered live (runner may pick it up)."""
    now = datetime.utcnow()
    fresh_id = await _insert_run(
        status=WorkflowRunStatus.PENDING,
        created_at=now - timedelta(seconds=10),
    )
    cleanup_runs.append(fresh_id)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    assert fresh_id not in stuck_ids


# ---------------------------------------------------------------------------
# Terminal statuses are never returned, regardless of timestamps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminal_statuses_never_returned(cleanup_runs):
    """COMPLETED / CANCELLED / FAILED rows are never reaped — even if they look 'stuck'."""
    now = datetime.utcnow()
    very_stale = now - timedelta(days=7)
    ids = []
    for terminal_status in (
        WorkflowRunStatus.COMPLETED,
        WorkflowRunStatus.CANCELLED,
        WorkflowRunStatus.FAILED,
    ):
        run_id = await _insert_run(
            status=terminal_status,
            created_at=very_stale,
            started_at=very_stale,
            heartbeat_at=very_stale,
        )
        ids.append(run_id)
    cleanup_runs.extend(ids)

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    for run_id in ids:
        assert run_id not in stuck_ids


# ---------------------------------------------------------------------------
# Mixed scenario — guards against the worst regressions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_predicate_returns_only_stuck_rows_in_mixed_scenario(cleanup_runs):
    """A combined fixture: stuck and healthy of every category. The predicate
    must select exactly the stuck ones and nothing else.

    This is the canary for or_/and_ swaps and cutoff-comparison bugs.
    """
    now = datetime.utcnow()

    stuck_running_stale_hb = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(hours=1),
        started_at=now - timedelta(hours=1),
        heartbeat_at=now - timedelta(seconds=RUNNING_GRACE * 2),
    )
    stuck_running_no_hb = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(seconds=RUNNING_GRACE * 2),
        started_at=now - timedelta(seconds=RUNNING_GRACE * 2),
        heartbeat_at=None,
    )
    stuck_pending = await _insert_run(
        status=WorkflowRunStatus.PENDING,
        created_at=now - timedelta(seconds=PENDING_GRACE * 2),
    )

    fresh_running = await _insert_run(
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(hours=1),
        started_at=now - timedelta(hours=1),
        heartbeat_at=now - timedelta(seconds=5),
    )
    fresh_pending = await _insert_run(
        status=WorkflowRunStatus.PENDING,
        created_at=now - timedelta(seconds=10),
    )
    completed_old = await _insert_run(
        status=WorkflowRunStatus.COMPLETED,
        created_at=now - timedelta(days=7),
        started_at=now - timedelta(days=7),
        heartbeat_at=now - timedelta(days=7),
    )

    cleanup_runs.extend([
        stuck_running_stale_hb,
        stuck_running_no_hb,
        stuck_pending,
        fresh_running,
        fresh_pending,
        completed_old,
    ])

    stuck = await _find_stuck_runs(RUNNING_GRACE, PENDING_GRACE)
    stuck_ids = {r.id for r in stuck}

    # The three stuck rows are returned
    assert stuck_running_stale_hb in stuck_ids
    assert stuck_running_no_hb in stuck_ids
    assert stuck_pending in stuck_ids

    # The three healthy / terminal rows are not
    assert fresh_running not in stuck_ids
    assert fresh_pending not in stuck_ids
    assert completed_old not in stuck_ids
