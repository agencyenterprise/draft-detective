"""Integration tests for the workflow gate service against real Postgres.

Covers the approval record itself (per project revision, idempotent) and the
release of runs awaiting approval once every gate they need is approved.
"""

import uuid
from typing import Sequence

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_gate_approval import WorkflowGateApproval
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.workflow_gates import (
    _gates_satisfied,
    approve_gate,
    get_approved_gates,
    get_effective_gates,
    get_unsatisfied_gates,
    release_runs_awaiting_approval,
)
from lib.workflows.models import WorkflowGate, WorkflowRunType


class Seeder:
    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.project_ids: list[uuid.UUID] = []

    async def user(self) -> User:
        user = User(
            id=uuid.uuid4(),
            email=f"gates-{uuid.uuid4()}@example.com",
            name="Gates Tester",
            role=UserRole.USER,
            show_experimental_features=False,
        )
        async with get_async_db_session() as session:
            session.add(user)
            await session.commit()
        self.user_ids.append(user.id)
        return user

    async def project(self, user: User, *, current_revision: int = 1) -> Project:
        project = Project(
            id=uuid.uuid4(),
            title="Gated project",
            user_id=user.id,
            current_revision=current_revision,
        )
        async with get_async_db_session() as session:
            session.add(project)
            await session.commit()
        self.project_ids.append(project.id)
        return project

    async def runs(
        self,
        project: Project,
        rows: Sequence[tuple[WorkflowRunType, int, WorkflowRunStatus]],
    ) -> list[uuid.UUID]:
        ids: list[uuid.UUID] = []
        async with get_async_db_session() as session:
            for wf_type, revision, status in rows:
                run_id = uuid.uuid4()
                session.add(
                    WorkflowRun(
                        id=run_id,
                        project_id=project.id,
                        type=wf_type,
                        langgraph_thread_id=str(uuid.uuid4()),
                        status=status,
                        revision=revision,
                    )
                )
                ids.append(run_id)
            await session.commit()
        return ids

    async def cleanup(self) -> None:
        # workflow_runs and workflow_gate_approvals go with the project via
        # ON DELETE CASCADE.
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


async def _approval_rows(project_id: uuid.UUID) -> list[WorkflowGateApproval]:
    async with get_async_db_session() as session:
        return list(
            (
                await session.execute(
                    select(WorkflowGateApproval).where(
                        col(WorkflowGateApproval.project_id) == project_id
                    )
                )
            )
            .scalars()
            .all()
        )


# ---------------------------------------------------------------------------
# Effective gates (pure, from manifests)
# ---------------------------------------------------------------------------


def test_claim_reference_validation_is_gated_on_reference_review():
    assert get_effective_gates(WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2) == [
        WorkflowGate.REFERENCE_REVIEW
    ]


def test_ungated_workflows_have_no_effective_gates():
    assert get_effective_gates(WorkflowRunType.DOCUMENT_PROCESSING) == []
    assert get_effective_gates(WorkflowRunType.REFERENCE_FILE_MATCHING) == []


def test_gates_satisfied_follows_the_approved_set():
    assert (
        _gates_satisfied(WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2, set()) is False
    )
    assert (
        _gates_satisfied(
            WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            {WorkflowGate.REFERENCE_REVIEW},
        )
        is True
    )
    # Accepts the raw slug a database row carries.
    assert _gates_satisfied("document_processing", set()) is True


def test_gates_satisfied_never_releases_a_retired_workflow():
    """A row whose slug no longer maps to a workflow has nothing to start."""
    assert _gates_satisfied("human_approval", {WorkflowGate.REFERENCE_REVIEW}) is False


# ---------------------------------------------------------------------------
# Approval record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_is_unsatisfied_until_approved(seeder):
    user = await seeder.user()
    project = await seeder.project(user)
    project_id = str(project.id)

    assert await get_unsatisfied_gates(
        project_id, 1, WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    ) == [WorkflowGate.REFERENCE_REVIEW]

    await approve_gate(project_id, 1, WorkflowGate.REFERENCE_REVIEW, user.id)

    assert (
        await get_unsatisfied_gates(
            project_id, 1, WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
        )
        == []
    )
    assert await get_approved_gates(project_id, 1) == {WorkflowGate.REFERENCE_REVIEW}


@pytest.mark.asyncio
async def test_approve_gate_is_idempotent(seeder):
    user = await seeder.user()
    project = await seeder.project(user)

    await approve_gate(str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, user.id)
    await approve_gate(str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, user.id)

    rows = await _approval_rows(project.id)
    assert len(rows) == 1
    assert rows[0].gate == WorkflowGate.REFERENCE_REVIEW
    assert rows[0].approved_by_user_id == user.id


@pytest.mark.asyncio
async def test_approval_is_scoped_to_the_revision(seeder):
    """A new revision means a new document: the review is asked again."""
    user = await seeder.user()
    project = await seeder.project(user, current_revision=2)

    await approve_gate(str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, user.id)

    assert await get_approved_gates(str(project.id), 1) == {
        WorkflowGate.REFERENCE_REVIEW
    }
    assert await get_approved_gates(str(project.id), 2) == set()


# ---------------------------------------------------------------------------
# Releasing runs awaiting approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_moves_awaiting_runs_to_pending_once_approved(seeder):
    user = await seeder.user()
    project = await seeder.project(user)
    (awaiting_id,) = await seeder.runs(
        project,
        [
            (
                WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
                1,
                WorkflowRunStatus.AWAITING_APPROVAL,
            )
        ],
    )

    # Nothing approved yet: the run keeps waiting.
    assert await release_runs_awaiting_approval(str(project.id), 1) == []
    assert await _status_of(awaiting_id) == WorkflowRunStatus.AWAITING_APPROVAL

    await approve_gate(str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, user.id)
    released = await release_runs_awaiting_approval(str(project.id), 1)

    assert [r.id for r in released] == [awaiting_id]
    assert released[0].status == WorkflowRunStatus.PENDING
    assert await _status_of(awaiting_id) == WorkflowRunStatus.PENDING


@pytest.mark.asyncio
async def test_release_leaves_other_revisions_and_non_awaiting_runs_alone(seeder):
    user = await seeder.user()
    project = await seeder.project(user, current_revision=2)
    rev1_awaiting, rev2_awaiting, rev1_pending, rev1_done = await seeder.runs(
        project,
        [
            (
                WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
                1,
                WorkflowRunStatus.AWAITING_APPROVAL,
            ),
            (
                WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
                2,
                WorkflowRunStatus.AWAITING_APPROVAL,
            ),
            (WorkflowRunType.DOCUMENT_PROCESSING, 1, WorkflowRunStatus.PENDING),
            (WorkflowRunType.REFERENCE_FILE_MATCHING, 1, WorkflowRunStatus.COMPLETED),
        ],
    )

    await approve_gate(str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, user.id)
    released = await release_runs_awaiting_approval(str(project.id), 1)

    assert [r.id for r in released] == [rev1_awaiting]
    assert await _status_of(rev1_awaiting) == WorkflowRunStatus.PENDING
    assert await _status_of(rev2_awaiting) == WorkflowRunStatus.AWAITING_APPROVAL
    assert await _status_of(rev1_pending) == WorkflowRunStatus.PENDING
    assert await _status_of(rev1_done) == WorkflowRunStatus.COMPLETED


@pytest.mark.asyncio
async def test_release_is_a_no_op_when_run_twice(seeder):
    user = await seeder.user()
    project = await seeder.project(user)
    await seeder.runs(
        project,
        [
            (
                WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
                1,
                WorkflowRunStatus.AWAITING_APPROVAL,
            )
        ],
    )
    await approve_gate(str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, user.id)

    first = await release_runs_awaiting_approval(str(project.id), 1)
    second = await release_runs_awaiting_approval(str(project.id), 1)

    assert len(first) == 1
    assert second == []
