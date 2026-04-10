"""Unit tests for create_new_revision service function."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.issue import IssueStatus
from lib.models.project import AccessLevel, Project
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.projects import create_new_revision


def _make_project(current_revision: int = 1) -> Project:
    return Project(
        id=uuid.uuid4(),
        title="Test Project",
        user_id=uuid.uuid4(),
        current_revision=current_revision,
    )


def _make_run(
    project_id: uuid.UUID,
    run_type: WorkflowRunType,
    status: WorkflowRunStatus,
    revision: int = 1,
) -> WorkflowRun:
    return WorkflowRun(
        id=uuid.uuid4(),
        project_id=str(project_id),
        type=run_type,
        status=status,
        revision=revision,
        langgraph_thread_id=str(uuid.uuid4()),
    )


class _FakeSession:
    """Minimal async session stub that records execute calls."""

    def __init__(self, scalars_result=None, all_result=None):
        self._scalars_result = scalars_result or []
        self._all_result = all_result or []
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = self._scalars_result
        mock_result.scalars.return_value = mock_scalars
        mock_result.all.return_value = self._all_result
        return mock_result

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_create_new_revision_increments_revision():
    """create_new_revision should return old_revision + 1."""
    project = _make_project(current_revision=1)

    # First session: fetching active runs (none)
    # Second session: collecting types, archiving issues, updating project
    sessions = [
        _FakeSession(scalars_result=[]),
        _FakeSession(all_result=[]),
    ]
    session_iter = iter(sessions)

    with (
        patch(
            "lib.services.projects.get_project_access",
            new=AsyncMock(return_value=(project, AccessLevel.WRITE)),
        ),
        patch(
            "lib.services.projects.get_async_db_session",
            side_effect=lambda: next(session_iter),
        ),
    ):
        new_revision, _ = await create_new_revision(str(project.id), MagicMock())

    assert new_revision == 2


@pytest.mark.asyncio
async def test_create_new_revision_from_revision_3():
    """create_new_revision on a project at revision 3 should return 4."""
    project = _make_project(current_revision=3)

    sessions = [
        _FakeSession(scalars_result=[]),
        _FakeSession(all_result=[]),
    ]
    session_iter = iter(sessions)

    with (
        patch(
            "lib.services.projects.get_project_access",
            new=AsyncMock(return_value=(project, AccessLevel.WRITE)),
        ),
        patch(
            "lib.services.projects.get_async_db_session",
            side_effect=lambda: next(session_iter),
        ),
    ):
        new_revision, _ = await create_new_revision(str(project.id), MagicMock())

    assert new_revision == 4


@pytest.mark.asyncio
async def test_create_new_revision_cancels_active_workflows():
    """Active (PENDING/RUNNING) workflows for the old revision should be cancelled."""
    project = _make_project(current_revision=1)
    pending_run = _make_run(
        project.id, WorkflowRunType.CLAIM_EXTRACTION, WorkflowRunStatus.PENDING
    )
    running_run = _make_run(
        project.id, WorkflowRunType.REFERENCE_EXTRACTION, WorkflowRunStatus.RUNNING
    )

    sessions = [
        _FakeSession(scalars_result=[pending_run, running_run]),
        _FakeSession(all_result=[]),
    ]
    session_iter = iter(sessions)

    mock_cancel = AsyncMock()

    with (
        patch(
            "lib.services.projects.get_project_access",
            new=AsyncMock(return_value=(project, AccessLevel.WRITE)),
        ),
        patch(
            "lib.services.projects.get_async_db_session",
            side_effect=lambda: next(session_iter),
        ),
        patch(
            "lib.services.projects.cancel_workflow_run",
            new=mock_cancel,
        ),
    ):
        await create_new_revision(str(project.id), MagicMock())

    assert mock_cancel.await_count == 2
    cancelled_ids = {call.args[0] for call in mock_cancel.await_args_list}
    assert str(pending_run.id) in cancelled_ids
    assert str(running_run.id) in cancelled_ids


@pytest.mark.asyncio
async def test_create_new_revision_returns_previous_workflow_types():
    """Should return the distinct workflow types from the old revision."""
    project = _make_project(current_revision=1)

    previous_types = [
        (WorkflowRunType.CLAIM_EXTRACTION,),
        (WorkflowRunType.REFERENCE_EXTRACTION,),
    ]

    sessions = [
        _FakeSession(scalars_result=[]),
        _FakeSession(all_result=previous_types),
    ]
    session_iter = iter(sessions)

    with (
        patch(
            "lib.services.projects.get_project_access",
            new=AsyncMock(return_value=(project, AccessLevel.WRITE)),
        ),
        patch(
            "lib.services.projects.get_async_db_session",
            side_effect=lambda: next(session_iter),
        ),
    ):
        _, returned_types = await create_new_revision(str(project.id), MagicMock())

    assert set(returned_types) == {
        WorkflowRunType.CLAIM_EXTRACTION,
        WorkflowRunType.REFERENCE_EXTRACTION,
    }


@pytest.mark.asyncio
async def test_create_new_revision_requires_write_access():
    """Should raise when user lacks WRITE access."""
    from fastapi import HTTPException

    with patch(
        "lib.services.projects.get_project_access",
        new=AsyncMock(side_effect=HTTPException(status_code=403, detail="Access denied")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_new_revision("some-project-id", MagicMock())

    assert exc_info.value.status_code == 403
