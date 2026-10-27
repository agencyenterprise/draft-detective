"""Integration tests for get_latest_workflow_run_state_by_type.

This helper backs the prior-state seeding for accumulating workflows. Its SQL
must: pick the most recent run of the type/revision that actually has a
persisted state, skip runs whose state_json is NULL (including the just-created
current run), honor exclude_run_id, and scope by type/revision. A regression
here would silently drop or mix run state, so these exercise real rows.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.service import get_latest_workflow_run_state_by_type
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)

TYPE = WorkflowRunType.REFERENCE_DOWNLOADER


def _state_json(project_id: uuid.UUID, ref_id: str) -> dict:
    """A valid ReferenceDownloaderState payload tagged with a reference id."""
    return ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER,
            project_id=str(project_id),
            references=[],
        ),
        fetched_references=[
            ReferenceFetchResult(
                reference_id=ref_id,
                input_reference=ref_id,
                status=ReferenceFetchStatus.COMPLETED,
            )
        ],
    ).model_dump(mode="json")


@pytest_asyncio.fixture
async def project_id():
    pid = uuid.uuid4()
    async with get_async_db_session() as session:
        session.add(Project(id=pid, title="Test Project"))
        await session.commit()

    yield pid

    # Deleting the project cascades to its workflow runs.
    async with get_async_db_session() as session:
        project = (
            await session.execute(select(Project).where(col(Project.id) == pid))
        ).scalar_one_or_none()
        if project:
            await session.delete(project)
            await session.commit()


async def _insert(
    project_id: uuid.UUID,
    *,
    status: WorkflowRunStatus,
    created_at: datetime,
    state_json: dict | None,
    revision: int = 1,
    type: WorkflowRunType = TYPE,
) -> uuid.UUID:
    run_id = uuid.uuid4()
    async with get_async_db_session() as session:
        session.add(
            WorkflowRun(
                id=run_id,
                langgraph_thread_id=str(uuid.uuid4()),
                project_id=project_id,
                type=type,
                status=status,
                revision=revision,
                created_at=created_at,
                state_json=state_json,
            )
        )
        await session.commit()
    return run_id


@pytest.mark.asyncio
async def test_returns_latest_run_with_state_skipping_null(project_id):
    """Returns the newest run that has state, skipping a newer NULL-state run."""
    now = datetime.utcnow()
    await _insert(
        project_id,
        status=WorkflowRunStatus.COMPLETED,
        created_at=now - timedelta(hours=2),
        state_json=_state_json(project_id, "old"),
    )
    await _insert(
        project_id,
        status=WorkflowRunStatus.COMPLETED,
        created_at=now - timedelta(hours=1),
        state_json=_state_json(project_id, "new"),
    )
    # The just-created current run: newest, but state_json still NULL.
    await _insert(
        project_id,
        status=WorkflowRunStatus.PENDING,
        created_at=now,
        state_json=None,
    )

    state = await get_latest_workflow_run_state_by_type(str(project_id), TYPE, 1)

    assert state is not None
    assert [r.reference_id for r in state.fetched_references] == ["new"]


@pytest.mark.asyncio
async def test_exclude_run_id_skips_that_run(project_id):
    """exclude_run_id falls through to the next-most-recent run with state."""
    now = datetime.utcnow()
    await _insert(
        project_id,
        status=WorkflowRunStatus.COMPLETED,
        created_at=now - timedelta(hours=2),
        state_json=_state_json(project_id, "old"),
    )
    newest = await _insert(
        project_id,
        status=WorkflowRunStatus.COMPLETED,
        created_at=now - timedelta(hours=1),
        state_json=_state_json(project_id, "new"),
    )

    state = await get_latest_workflow_run_state_by_type(
        str(project_id), TYPE, 1, exclude_run_id=str(newest)
    )

    assert state is not None
    assert [r.reference_id for r in state.fetched_references] == ["old"]


@pytest.mark.asyncio
async def test_returns_none_for_other_revision(project_id):
    """A run in a different revision is not visible."""
    await _insert(
        project_id,
        status=WorkflowRunStatus.COMPLETED,
        created_at=datetime.utcnow(),
        state_json=_state_json(project_id, "r1"),
        revision=1,
    )

    assert await get_latest_workflow_run_state_by_type(str(project_id), TYPE, 2) is None


@pytest.mark.asyncio
async def test_returns_none_when_no_run_has_state(project_id):
    """Only NULL-state runs exist → nothing to seed from."""
    await _insert(
        project_id,
        status=WorkflowRunStatus.PENDING,
        created_at=datetime.utcnow(),
        state_json=None,
    )

    assert await get_latest_workflow_run_state_by_type(str(project_id), TYPE, 1) is None
