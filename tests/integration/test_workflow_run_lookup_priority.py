"""Integration tests for how AWAITING_APPROVAL ranks in run lookups and revision changes.

The "most relevant run per type" queries decide what the UI shows and whether
the runner reuses a run or creates another. A run waiting on the user must be
found ahead of terminal runs, and behind anything that is actually working.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.projects import create_new_revision
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    get_project_workflow_runs,
)

CLAIM = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Seeder:
    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.project_ids: list[uuid.UUID] = []

    async def user(self) -> User:
        user = User(
            id=uuid.uuid4(),
            email=f"lookup-{uuid.uuid4()}@example.com",
            name="Lookup Tester",
            role=UserRole.USER,
            show_experimental_features=False,
        )
        async with get_async_db_session() as session:
            session.add(user)
            await session.commit()
        self.user_ids.append(user.id)
        return user

    async def project(self, user: User) -> Project:
        project = Project(
            id=uuid.uuid4(), title="Lookup project", user_id=user.id, current_revision=1
        )
        async with get_async_db_session() as session:
            session.add(project)
            await session.commit()
        self.project_ids.append(project.id)
        return project

    async def runs(
        self,
        project: Project,
        rows: Sequence[tuple[WorkflowRunType, WorkflowRunStatus]],
    ) -> list[uuid.UUID]:
        """Insert runs oldest-first so created_at ordering is deterministic."""
        ids: list[uuid.UUID] = []
        async with get_async_db_session() as session:
            for index, (wf_type, status) in enumerate(rows):
                run_id = uuid.uuid4()
                session.add(
                    WorkflowRun(
                        id=run_id,
                        project_id=project.id,
                        type=wf_type,
                        langgraph_thread_id=str(uuid.uuid4()),
                        status=status,
                        revision=1,
                        created_at=BASE_TIME + timedelta(minutes=index),
                    )
                )
                ids.append(run_id)
            await session.commit()
        return ids

    async def cleanup(self) -> None:
        async with get_async_db_session() as session:
            for project_id in self.project_ids:
                proj = (
                    await session.execute(
                        select(Project).where(col(Project.id) == project_id)
                    )
                ).scalar_one_or_none()
                if proj:
                    await session.delete(proj)
            for user_id in self.user_ids:
                usr = (
                    await session.execute(select(User).where(col(User.id) == user_id))
                ).scalar_one_or_none()
                if usr:
                    await session.delete(usr)
            await session.commit()


@pytest_asyncio.fixture
async def seeder():
    s = Seeder()
    yield s
    await s.cleanup()


async def _status_of(run_id: uuid.UUID) -> WorkflowRunStatus:
    async with get_async_db_session() as session:
        run = (
            await session.execute(
                select(WorkflowRun).where(col(WorkflowRun.id) == run_id)
            )
        ).scalar_one()
        return run.status


# ---------------------------------------------------------------------------
# get_project_workflow_run_by_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_awaiting_run_is_found_ahead_of_a_newer_completed_run(seeder):
    """Without this the runner would see 'completed' and create a duplicate run."""
    user = await seeder.user()
    project = await seeder.project(user)
    awaiting_id, _completed_id = await seeder.runs(
        project,
        [
            (CLAIM, WorkflowRunStatus.AWAITING_APPROVAL),
            (CLAIM, WorkflowRunStatus.COMPLETED),
        ],
    )

    run = await get_project_workflow_run_by_type(str(project.id), CLAIM, revision=1)

    assert run is not None and run.id == awaiting_id


@pytest.mark.asyncio
async def test_pending_and_running_rank_ahead_of_awaiting(seeder):
    user = await seeder.user()
    project = await seeder.project(user)
    _awaiting_id, pending_id = await seeder.runs(
        project,
        [
            (CLAIM, WorkflowRunStatus.AWAITING_APPROVAL),
            (CLAIM, WorkflowRunStatus.PENDING),
        ],
    )

    run = await get_project_workflow_run_by_type(str(project.id), CLAIM, revision=1)
    assert run is not None and run.id == pending_id

    (running_id,) = await seeder.runs(project, [(CLAIM, WorkflowRunStatus.RUNNING)])
    run = await get_project_workflow_run_by_type(str(project.id), CLAIM, revision=1)
    assert run is not None and run.id == running_id


# ---------------------------------------------------------------------------
# get_project_workflow_runs (one row per type)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_listing_shows_the_awaiting_run_for_its_type(seeder):
    user = await seeder.user()
    project = await seeder.project(user)
    awaiting_id, _, processing_id = await seeder.runs(
        project,
        [
            (CLAIM, WorkflowRunStatus.AWAITING_APPROVAL),
            (CLAIM, WorkflowRunStatus.CANCELLED),
            (WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.COMPLETED),
        ],
    )

    details = await get_project_workflow_runs(
        str(project.id), revision=1, include_internal=True
    )
    by_type = {detail.run.type: detail.run for detail in details}

    assert by_type[CLAIM].id == awaiting_id
    assert by_type[CLAIM].status == WorkflowRunStatus.AWAITING_APPROVAL
    assert by_type[WorkflowRunType.DOCUMENT_PROCESSING].id == processing_id


# ---------------------------------------------------------------------------
# New revision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_revision_cancels_a_run_awaiting_approval(seeder):
    """A run waiting on the old document must not be released against the new one."""
    user = await seeder.user()
    project = await seeder.project(user)
    awaiting_id, completed_id = await seeder.runs(
        project,
        [
            (CLAIM, WorkflowRunStatus.AWAITING_APPROVAL),
            (WorkflowRunType.DOCUMENT_PROCESSING, WorkflowRunStatus.COMPLETED),
        ],
    )

    new_revision, previous_types = await create_new_revision(str(project.id), user)

    assert new_revision == 2
    assert await _status_of(awaiting_id) == WorkflowRunStatus.CANCELLED
    assert await _status_of(completed_id) == WorkflowRunStatus.COMPLETED
    # Starting an assessment is the signal for re-running it, not finishing it.
    assert CLAIM in previous_types
