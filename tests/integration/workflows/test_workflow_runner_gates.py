"""Tests for how the workflow runner holds and releases gated workflows.

Claim Reference Validation is gated on the reference review. Until the gate
is approved for the project's revision, starting it must create the run in
AWAITING_APPROVAL and schedule nothing; once approved, it runs like any other
workflow. The MCP blocking path reports the awaiting workflow instead, or
records the approval on the caller's behalf when told to.
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_runner import (
    AutoRunWorkflowItem,
    WorkflowGateRequiredError,
    approve_project_gate,
    run_multiple_workflows_blocking,
    start_multiple_workflow_runs,
    start_workflow_run,
)
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2Config,
)
from lib.workflows.models import WorkflowGate
from lib.workflows.registry import get_config_type

CLAIM = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2


def _user() -> User:
    return User(id=uuid4(), email="gates@example.com", name="Gates")


def _project() -> MagicMock:
    project = MagicMock()
    project.id = uuid4()
    project.current_revision = 1
    return project


def _run(
    project_id, workflow_type: WorkflowRunType, status: WorkflowRunStatus
) -> WorkflowRun:
    return WorkflowRun(
        id=uuid4(),
        project_id=project_id,
        type=workflow_type,
        status=status,
        langgraph_thread_id=str(uuid4()),
        revision=1,
    )


class Harness:
    """Mocks every DB touch point of the runner and records what it did."""

    def __init__(
        self,
        *,
        approved: set[WorkflowGate] | None = None,
        existing: dict[WorkflowRunType, WorkflowRun] | None = None,
    ):
        self.project = _project()
        self.user = _user()
        self.approved = set(approved or set())
        self.existing = existing or {}
        self.created: list[dict] = []
        self.approve_gate = AsyncMock(side_effect=self._approve)
        self.update_status = AsyncMock()
        self.request = StartMultipleWorkflowsRequest(
            project_id=str(self.project.id), workflow_types=[CLAIM]
        )

    async def _approve(self, project_id, revision, gate, approved_by_user_id=None):
        self.approved.add(gate)

    async def _create_run(self, **kwargs):
        self.created.append(kwargs)
        return str(uuid4())

    async def _get_run(self, project_id, workflow_type, **kwargs):
        return self.existing.get(workflow_type)

    def _config(self, project, workflow_type, openai_api_key=None):
        return get_config_type(workflow_type)(project_id=str(self.project.id))

    def patches(self):
        return (
            patch(
                "lib.api.services.workflow_runner.get_project_access",
                new=AsyncMock(return_value=(self.project, AccessLevel.WRITE)),
            ),
            patch(
                "lib.api.services.workflow_runner.assert_project_has_main_file",
                new=AsyncMock(),
            ),
            patch(
                "lib.api.services.workflow_runner._assert_api_key_available",
                return_value=None,
            ),
            patch(
                "lib.api.services.workflow_runner.get_project_workflow_run_by_type",
                side_effect=self._get_run,
            ),
            patch(
                "lib.api.services.workflow_runner.create_workflow_run",
                new=AsyncMock(side_effect=self._create_run),
            ),
            patch(
                "lib.api.services.workflow_runner.create_workflow_config",
                side_effect=self._config,
            ),
            patch(
                "lib.api.services.workflow_runner.get_approved_gates",
                new=AsyncMock(side_effect=lambda *a, **k: set(self.approved)),
            ),
            patch(
                "lib.api.services.workflow_runner.approve_gate", new=self.approve_gate
            ),
            patch(
                "lib.api.services.workflow_runner.update_workflow_run_status",
                new=self.update_status,
            ),
            patch(
                "lib.api.services.workflow_runner.run_workflow_from_config",
                new=AsyncMock(),
            ),
        )

    def created_status(
        self, workflow_type: WorkflowRunType
    ) -> WorkflowRunStatus | None:
        for call in self.created:
            if call["type"] == workflow_type:
                return call["status"]
        return None


def _scheduled_items(background_tasks: BackgroundTasks) -> list[AutoRunWorkflowItem]:
    return [
        item
        for task in background_tasks.tasks
        for item in cast(list[AutoRunWorkflowItem], task.kwargs.get("items", []))
    ]


def _scheduled_types(background_tasks: BackgroundTasks) -> set[WorkflowRunType]:
    return {item.config.type for item in _scheduled_items(background_tasks)}


async def _start(harness: Harness) -> tuple[list[str], BackgroundTasks]:
    background_tasks = BackgroundTasks()
    with _stack(harness.patches()):
        run_ids = await start_multiple_workflow_runs(
            workflow_types=[CLAIM],
            request=harness.request,
            user=harness.user,
            background_tasks=background_tasks,
        )
    return run_ids, background_tasks


class _stack:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        return False


# ---------------------------------------------------------------------------
# UI path: start_multiple_workflow_runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gated_workflow_awaits_approval_and_is_not_scheduled():
    harness = Harness()

    run_ids, background_tasks = await _start(harness)

    assert harness.created_status(CLAIM) == WorkflowRunStatus.AWAITING_APPROVAL
    scheduled = _scheduled_types(background_tasks)
    assert CLAIM not in scheduled
    # Upstream prep still runs so the user has references to review.
    assert WorkflowRunType.REFERENCE_FILE_MATCHING in scheduled
    assert WorkflowRunType.DOCUMENT_PROCESSING in scheduled
    # The awaiting run is part of the batch the caller is told about.
    assert len(run_ids) == len(scheduled) + 1
    harness.approve_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_gated_workflow_runs_normally_once_gate_is_approved():
    harness = Harness(approved={WorkflowGate.REFERENCE_REVIEW})

    _, background_tasks = await _start(harness)

    assert harness.created_status(CLAIM) == WorkflowRunStatus.PENDING
    assert CLAIM in _scheduled_types(background_tasks)


@pytest.mark.asyncio
async def test_starting_again_reuses_the_awaiting_run():
    project_id = uuid4()
    awaiting = _run(project_id, CLAIM, WorkflowRunStatus.AWAITING_APPROVAL)
    harness = Harness(existing={CLAIM: awaiting})

    run_ids, background_tasks = await _start(harness)

    assert harness.created_status(CLAIM) is None
    assert str(awaiting.id) in run_ids
    assert CLAIM not in _scheduled_types(background_tasks)


@pytest.mark.asyncio
async def test_awaiting_run_is_released_in_place_when_gate_was_approved_meanwhile():
    project_id = uuid4()
    awaiting = _run(project_id, CLAIM, WorkflowRunStatus.AWAITING_APPROVAL)
    harness = Harness(
        approved={WorkflowGate.REFERENCE_REVIEW}, existing={CLAIM: awaiting}
    )

    run_ids, background_tasks = await _start(harness)

    assert harness.created_status(CLAIM) is None
    harness.update_status.assert_awaited_once_with(
        str(awaiting.id), WorkflowRunStatus.PENDING
    )
    assert str(awaiting.id) in run_ids
    assert str(awaiting.id) in {
        item.workflow_run_id for item in _scheduled_items(background_tasks)
    }


# ---------------------------------------------------------------------------
# MCP path: run_multiple_workflows_blocking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocking_path_reports_the_awaiting_workflow_and_creates_its_run():
    harness = Harness()

    with _stack(harness.patches()):
        with pytest.raises(WorkflowGateRequiredError) as exc_info:
            await run_multiple_workflows_blocking(
                [CLAIM], harness.request, harness.user
            )

    assert exc_info.value.pending_human_approval == [CLAIM]
    assert exc_info.value.pending_web_search == []
    # The run row exists so the web UI shows the review banner too.
    assert harness.created_status(CLAIM) == WorkflowRunStatus.AWAITING_APPROVAL
    harness.approve_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocking_path_records_the_approval_when_told_to():
    harness = Harness()

    with _stack(harness.patches()):
        await run_multiple_workflows_blocking(
            [CLAIM], harness.request, harness.user, approve_human_steps=True
        )

    harness.approve_gate.assert_awaited_once()
    args = harness.approve_gate.await_args
    assert args.args[2] == WorkflowGate.REFERENCE_REVIEW
    assert args.kwargs["approved_by_user_id"] == harness.user.id
    assert harness.created_status(CLAIM) == WorkflowRunStatus.PENDING


# ---------------------------------------------------------------------------
# Approving a gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_project_gate_schedules_released_runs():
    project = _project()
    user = _user()
    released = _run(project.id, CLAIM, WorkflowRunStatus.PENDING)
    background_tasks = BackgroundTasks()

    with (
        patch(
            "lib.api.services.workflow_runner.approve_gate", new=AsyncMock()
        ) as approve,
        patch(
            "lib.api.services.workflow_runner.release_runs_awaiting_approval",
            new=AsyncMock(return_value=[released]),
        ) as release,
        patch(
            "lib.api.services.workflow_runner.create_workflow_config",
            side_effect=lambda p, t, k=None: get_config_type(t)(
                project_id=str(project.id)
            ),
        ),
    ):
        run_ids = await approve_project_gate(
            project, WorkflowGate.REFERENCE_REVIEW, user, background_tasks
        )

    approve.assert_awaited_once_with(
        str(project.id), 1, WorkflowGate.REFERENCE_REVIEW, approved_by_user_id=user.id
    )
    release.assert_awaited_once_with(str(project.id), 1)
    assert run_ids == [str(released.id)]
    assert len(background_tasks.tasks) == 1
    (item,) = _scheduled_items(background_tasks)
    assert item.workflow_run_id == str(released.id)
    assert item.thread_id == released.langgraph_thread_id
    assert item.config.type == CLAIM


@pytest.mark.asyncio
async def test_approve_project_gate_with_nothing_awaiting_schedules_nothing():
    project = _project()
    background_tasks = BackgroundTasks()

    with (
        patch("lib.api.services.workflow_runner.approve_gate", new=AsyncMock()),
        patch(
            "lib.api.services.workflow_runner.release_runs_awaiting_approval",
            new=AsyncMock(return_value=[]),
        ),
    ):
        run_ids = await approve_project_gate(
            project, WorkflowGate.REFERENCE_REVIEW, _user(), background_tasks
        )

    assert run_ids == []
    assert background_tasks.tasks == []


# ---------------------------------------------------------------------------
# Single-workflow start: start_workflow_run
# ---------------------------------------------------------------------------


async def _start_single(
    unsatisfied: list[WorkflowGate],
) -> tuple[list[dict], BackgroundTasks]:
    harness = Harness()
    config = ClaimReferenceValidationV2Config(
        type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
        project_id=str(harness.project.id),
    )
    background_tasks = BackgroundTasks()
    with (
        _stack(harness.patches()),
        patch(
            "lib.api.services.workflow_runner.get_unsatisfied_gates",
            new=AsyncMock(return_value=unsatisfied),
        ),
    ):
        await start_workflow_run(config, harness.user, background_tasks)
    return harness.created, background_tasks


@pytest.mark.asyncio
async def test_single_start_parks_a_gated_workflow_without_scheduling_it():
    created, background_tasks = await _start_single([WorkflowGate.REFERENCE_REVIEW])

    assert [c["status"] for c in created] == [WorkflowRunStatus.AWAITING_APPROVAL]
    assert background_tasks.tasks == []


@pytest.mark.asyncio
async def test_single_start_schedules_the_workflow_once_its_gate_is_approved():
    created, background_tasks = await _start_single([])

    assert [c["status"] for c in created] == [WorkflowRunStatus.PENDING]
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["workflow_run_id"]
