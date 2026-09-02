"""Unit tests for the project gate approval endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from lib.api.routers.workflows import approve_project_gate_endpoint
from lib.models.project import AccessLevel
from lib.workflows.models import WorkflowGate


def _project(revision: int = 3) -> MagicMock:
    project = MagicMock()
    project.id = uuid.uuid4()
    project.current_revision = revision
    return project


def _user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.mark.asyncio
async def test_approve_returns_released_runs_for_the_current_revision():
    project = _project(revision=3)
    user = _user()
    background_tasks = BackgroundTasks()

    with (
        patch(
            "lib.api.routers.workflows.get_project_access",
            new=AsyncMock(return_value=(project, AccessLevel.WRITE)),
        ) as access,
        patch(
            "lib.api.routers.workflows.approve_project_gate",
            new=AsyncMock(return_value=["run-1", "run-2"]),
        ) as approve,
    ):
        response = await approve_project_gate_endpoint(
            str(project.id),
            WorkflowGate.REFERENCE_REVIEW,
            background_tasks,
            current_user=user,
        )

    access.assert_awaited_once_with(
        str(project.id), user=user, required_level=AccessLevel.WRITE
    )
    approve.assert_awaited_once_with(
        project, WorkflowGate.REFERENCE_REVIEW, user, background_tasks
    )
    assert response.gate == WorkflowGate.REFERENCE_REVIEW
    assert response.revision == 3
    assert response.released_workflow_run_ids == ["run-1", "run-2"]


@pytest.mark.asyncio
async def test_approve_requires_write_access():
    """A viewer cannot approve on the owner's behalf; the access check's error propagates untouched."""
    user = _user()

    with (
        patch(
            "lib.api.routers.workflows.get_project_access",
            new=AsyncMock(
                side_effect=HTTPException(status_code=403, detail="Access denied")
            ),
        ),
        patch(
            "lib.api.routers.workflows.approve_project_gate", new=AsyncMock()
        ) as approve,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await approve_project_gate_endpoint(
                str(uuid.uuid4()),
                WorkflowGate.REFERENCE_REVIEW,
                BackgroundTasks(),
                current_user=user,
            )

    assert exc_info.value.status_code == 403
    approve.assert_not_awaited()
