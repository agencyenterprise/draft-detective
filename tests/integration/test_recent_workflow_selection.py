"""Integration tests for get_recent_workflow_selection.

Covers the reconstruction of "what did this user pick last time" from the
workflow_runs rows, which are dependency-expanded and therefore hold a lot more
than the user's checkbox selection.
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
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_types import get_recent_workflow_selection
from lib.workflows.models import WorkflowRunType

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Seeder:
    """Creates users/projects/runs and remembers them for teardown."""

    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.project_ids: list[uuid.UUID] = []

    async def user(self) -> User:
        user = User(
            id=uuid.uuid4(),
            email=f"recent-selection-{uuid.uuid4()}@example.com",
            name="Recent Selection Tester",
            role=UserRole.USER,
            show_experimental_features=False,
        )
        async with get_async_db_session() as session:
            session.add(user)
            await session.commit()
        self.user_ids.append(user.id)
        return user

    async def project(
        self,
        user: User,
        *,
        age_days: int,
        runs: Sequence[tuple[WorkflowRunType, int]] = (),
        current_revision: int = 1,
    ) -> Project:
        """A project `age_days` old with `runs` as (type, revision) pairs."""
        project = Project(
            id=uuid.uuid4(),
            title=f"Project -{age_days}d",
            user_id=user.id,
            current_revision=current_revision,
            created_at=BASE_TIME - timedelta(days=age_days),
        )
        async with get_async_db_session() as session:
            session.add(project)
            await session.commit()
        self.project_ids.append(project.id)

        async with get_async_db_session() as session:
            for wf_type, revision in runs:
                session.add(
                    WorkflowRun(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        type=wf_type,
                        langgraph_thread_id=str(uuid.uuid4()),
                        status=WorkflowRunStatus.COMPLETED,
                        revision=revision,
                    )
                )
            await session.commit()
        return project

    async def cleanup(self) -> None:
        # workflow_runs go with the project via the FK's ON DELETE CASCADE.
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


@pytest.mark.asyncio
async def test_returns_only_the_most_recent_projects_assessments(seeder):
    """An older project's selection must not leak into the newer one's."""
    user = await seeder.user()
    await seeder.project(
        user,
        age_days=10,
        runs=[(WorkflowRunType.REVIEWER_2, 1), (WorkflowRunType.DOCUMENT_STRUCTURE, 1)],
    )
    await seeder.project(
        user,
        age_days=1,
        runs=[
            (WorkflowRunType.FIGURES_TABLES_CHECK, 1),
            (WorkflowRunType.ADVOCACY_TONE_V2, 1),
        ],
    )

    result = await get_recent_workflow_selection(user)

    assert set(result.workflow_types) == {
        WorkflowRunType.FIGURES_TABLES_CHECK,
        WorkflowRunType.ADVOCACY_TONE_V2,
    }


@pytest.mark.asyncio
async def test_strips_internal_and_dependency_runs(seeder):
    """The rows a project accumulates are dependency-expanded; only the picker-visible ones come back."""
    user = await seeder.user()
    await seeder.project(
        user,
        age_days=1,
        runs=[
            (WorkflowRunType.DOCUMENT_PROCESSING, 1),
            (WorkflowRunType.DOCUMENT_SUMMARIZATION, 1),
            (WorkflowRunType.REFERENCE_EXTRACTION, 1),
            (WorkflowRunType.REFERENCE_FILE_MATCHING, 1),
            (WorkflowRunType.REFERENCE_VALIDATION_V2, 1),
            (WorkflowRunType.RECOMMENDATION_CHECK, 1),
        ],
    )

    result = await get_recent_workflow_selection(user)

    assert set(result.workflow_types) == {
        WorkflowRunType.REFERENCE_VALIDATION_V2,
        WorkflowRunType.RECOMMENDATION_CHECK,
    }


@pytest.mark.asyncio
async def test_skips_a_project_with_no_picker_visible_runs(seeder):
    """The wizard's own just-created project (document processing only) must not shadow the last real one."""
    user = await seeder.user()
    await seeder.project(
        user, age_days=5, runs=[(WorkflowRunType.INFERENCE_VALIDATION_V2, 1)]
    )
    await seeder.project(
        user, age_days=0, runs=[(WorkflowRunType.DOCUMENT_PROCESSING, 1)]
    )

    result = await get_recent_workflow_selection(user)

    assert result.workflow_types == [WorkflowRunType.INFERENCE_VALIDATION_V2]


@pytest.mark.asyncio
async def test_no_history_returns_empty(seeder):
    """A brand-new user gets nothing, leaving the caller to apply its own default."""
    user = await seeder.user()

    assert (await get_recent_workflow_selection(user)).workflow_types == []

    # A project with no runs at all behaves the same.
    await seeder.project(user, age_days=0)
    assert (await get_recent_workflow_selection(user)).workflow_types == []


@pytest.mark.asyncio
async def test_other_users_projects_are_excluded(seeder):
    """The lookup is scoped to the caller, even when someone else's project is newer."""
    user = await seeder.user()
    other = await seeder.user()
    await seeder.project(user, age_days=5, runs=[(WorkflowRunType.REVIEWER_2, 1)])
    await seeder.project(
        other, age_days=0, runs=[(WorkflowRunType.ABBREVIATION_SCAN_V2, 1)]
    )

    result = await get_recent_workflow_selection(user)

    assert result.workflow_types == [WorkflowRunType.REVIEWER_2]


@pytest.mark.asyncio
async def test_dedupes_across_reruns_and_revisions(seeder):
    """Repeat runs collapse, and a later revision's assessments still count."""
    user = await seeder.user()
    await seeder.project(
        user,
        age_days=1,
        current_revision=2,
        runs=[
            (WorkflowRunType.REFERENCE_VALIDATION_V2, 1),
            (WorkflowRunType.REFERENCE_VALIDATION_V2, 1),
            (WorkflowRunType.REFERENCE_VALIDATION_V2, 2),
            (WorkflowRunType.RECOMMENDATION_CHECK, 2),
            (WorkflowRunType.FIGURES_TABLES_CHECK, 2),
        ],
    )

    result = await get_recent_workflow_selection(user)

    # Ordered by WORKFLOW_DISPLAY_CONFIG position, not by insertion order.
    assert result.workflow_types == [
        WorkflowRunType.REFERENCE_VALIDATION_V2,
        WorkflowRunType.RECOMMENDATION_CHECK,
        WorkflowRunType.FIGURES_TABLES_CHECK,
    ]
