"""Integration tests verifying WorkflowRun.state_json is deferred-load.

Loading the column eagerly would haul potentially large JSONB blobs (p99 ≈ 3 MB
on production-shaped data) through every SELECT against workflow_runs, hurting
the reaper, status checks, list endpoints, and so on. The mapper override in
lib/models/workflow_run.py marks state_json as deferred; these tests pin that
behavior so a future SQLAlchemy/SQLModel upgrade can't silently undo it.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.orm import undefer
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunType,
)


@pytest_asyncio.fixture
async def run_with_state():
    """Create a WorkflowRun with a non-trivial state_json payload."""
    run_id = uuid.uuid4()
    payload = {
        "type": "document_processing",
        "errors": [],
        "marker": "deferred-load-test",
        # Padding to make the payload obviously not-cheap to load.
        "blob": "x" * 50_000,
    }

    async with get_async_db_session() as session:
        run = WorkflowRun(
            id=run_id,
            langgraph_thread_id=str(uuid.uuid4()),
            project_id=None,
            type=WorkflowRunType.DOCUMENT_PROCESSING,
            status=WorkflowRunStatus.COMPLETED,
            state_json=payload,
        )
        session.add(run)
        await session.commit()

    yield str(run_id), payload

    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
        run = (await session.execute(stmt)).scalar_one_or_none()
        if run:
            await session.delete(run)
            await session.commit()


def test_mapper_strategy_is_deferred():
    """The mapper-level strategy must be deferred; without this, every SELECT
    on workflow_runs eagerly fetches the JSONB blob.
    """
    prop = inspect(WorkflowRun).attrs.state_json
    assert prop.strategy_key == (("deferred", True), ("instrument", True))


@pytest.mark.asyncio
async def test_state_json_not_loaded_by_default(run_with_state):
    """A vanilla SELECT must leave state_json in the unloaded set."""
    run_id, _ = run_with_state

    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
        run = (await session.execute(stmt)).scalar_one()

        unloaded = inspect(run).unloaded
        assert "state_json" in unloaded, (
            "state_json must be deferred — it should not be loaded by a basic SELECT. "
            f"Currently loaded: {set(WorkflowRun.model_fields) - unloaded}"
        )

        # Other columns should be present (e.g. status was selected normally).
        assert "status" not in unloaded


@pytest.mark.asyncio
async def test_undefer_loads_state_json_in_one_query(run_with_state):
    """Callers that need state opt in via undefer(); the row should arrive
    with state_json already populated, no separate fetch required.
    """
    run_id, payload = run_with_state

    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun)
            .where(col(WorkflowRun.id) == run_id)
            .options(undefer(col(WorkflowRun.state_json)))
        )
        run = (await session.execute(stmt)).scalar_one()

        assert "state_json" not in inspect(run).unloaded
        assert run.state_json is not None
        assert run.state_json["marker"] == payload["marker"]


@pytest.mark.asyncio
async def test_state_json_lazy_loads_via_refresh(run_with_state):
    """A deferred attribute can be loaded post-hoc via session.refresh; the
    row arrives without state_json, then gets it on demand.
    """
    run_id, payload = run_with_state

    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
        run = (await session.execute(stmt)).scalar_one()

        assert "state_json" in inspect(run).unloaded

        # Async-safe equivalent of touching the deferred attribute: refresh()
        # tells SQLAlchemy to fetch the named columns. Plain attribute access
        # would trigger sync IO from async context, which the asyncio engine
        # rejects — so production callers will either undefer at query time
        # or refresh explicitly.
        await session.refresh(run, ["state_json"])

        assert run.state_json is not None
        assert run.state_json["marker"] == payload["marker"]
        assert "state_json" not in inspect(run).unloaded
