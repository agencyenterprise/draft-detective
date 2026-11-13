"""How the start paths treat gated workflows and consent.

A start never schedules anything itself: it creates (or joins) the runs and
calls the promoter, which parks a gated run once its gate is all that holds it
back (see tests/integration/workflow_runs/test_promoter.py). What is left here
is the batch planning around gates and the MCP blocking path: it records an
approval when told to, asks for web-search consent before anything starts,
waits for the batch to settle, and reports the gated workflows with how the
rest ended.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_batch import WorkflowGateRequiredError
from lib.api.services.workflow_runner import (
    approve_project_gate,
    run_multiple_workflows_blocking,
    start_multiple_workflow_runs,
)
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.promoter import Promotion
from lib.services.workflow_runs.start import RunStart
from lib.workflows.models import WorkflowGate
from lib.workflows.registry import get_config_type

CLAIM = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
EXTRACTION = WorkflowRunType.REFERENCE_EXTRACTION
DOCS = WorkflowRunType.DOCUMENT_PROCESSING
REF_VALIDATION = WorkflowRunType.REFERENCE_VALIDATION_V2
ABBREVIATIONS = WorkflowRunType.ABBREVIATION_SCAN_V2
BATCH = "lib.api.services.workflow_batch"
RUNNER = "lib.api.services.workflow_runner"


def _run(workflow_type: WorkflowRunType, status: WorkflowRunStatus) -> WorkflowRun:
    return WorkflowRun(
        id=uuid4(),
        type=workflow_type,
        status=status,
        langgraph_thread_id=str(uuid4()),
        revision=1,
    )


class Harness:
    """Mocks every DB touch point of the start paths and records what they did."""

    def __init__(
        self,
        *,
        approved: set[WorkflowGate] | None = None,
        existing: dict[WorkflowRunType, WorkflowRun] | None = None,
    ):
        self.project = Project(id=uuid4(), user_id=uuid4(), title="gates")
        self.user = User(id=uuid4(), email="gates@example.com", name="Gates")
        self.approved = set(approved or set())
        self.existing = existing or {}
        # Run id per type the start created or joined, in start order.
        self.started: dict[WorkflowRunType, str] = {}
        self.approve_gate = AsyncMock(side_effect=self._approve)
        self.promote = AsyncMock(return_value=Promotion())
        self.settle = AsyncMock()
        # Status the blocking path reads back per run id once the batch settles.
        self.run_statuses: dict[str, WorkflowRunStatus] = {}
        self.request = StartMultipleWorkflowsRequest(
            project_id=str(self.project.id), workflow_types=[CLAIM]
        )

    async def _approve(self, project_id, revision, gate, approved_by_user_id=None):
        self.approved.add(gate)

    async def _start_or_join(self, config, workflow_type, revision, *, started_by):
        run_id = str(uuid4())
        self.started[workflow_type] = run_id
        return RunStart(run_id=run_id, status=WorkflowRunStatus.PENDING, created=True)

    async def _status(self, run_id: str) -> WorkflowRunStatus:
        return self.run_statuses.get(run_id, WorkflowRunStatus.COMPLETED)

    async def _existing(self, project_id, workflow_type, **kwargs):
        return self.existing.get(workflow_type)

    def _config(self, project, workflow_type, openai_api_key=None, model=None):
        return get_config_type(workflow_type).model_validate(
            {"project_id": str(project.id), "type": workflow_type, "model": model}
        )

    def patches(self) -> ExitStack:
        stack = ExitStack()
        targets: dict[str, dict[str, object]] = {
            f"{BATCH}.authorized_project": {
                "new": AsyncMock(return_value=self.project)
            },
            f"{BATCH}.assert_api_key_available": {"return_value": None},
            f"{BATCH}.get_project_workflow_run_by_type": {
                "side_effect": self._existing
            },
            f"{BATCH}.create_workflow_config": {"side_effect": self._config},
            f"{BATCH}.get_approved_gates": {
                "new": AsyncMock(side_effect=lambda *a, **k: set(self.approved))
            },
            f"{BATCH}.approve_gate": {"new": self.approve_gate},
            f"{RUNNER}.approve_gate": {"new": self.approve_gate},
            f"{RUNNER}.start_or_join_run": {
                "new": AsyncMock(side_effect=self._start_or_join)
            },
            f"{RUNNER}.promote_ready_runs": {"new": self.promote},
            f"{RUNNER}.wait_for_runs_to_settle": {"new": self.settle},
            f"{RUNNER}.get_workflow_run_status": {
                "new": AsyncMock(side_effect=self._status)
            },
        }
        for target, kwargs in targets.items():
            stack.enter_context(patch(target, **kwargs))  # type: ignore[call-overload]  # patch's kwargs are untyped
        return stack

    async def blocking(self, workflow_types: list[WorkflowRunType], **kwargs):
        with self.patches():
            return await run_multiple_workflows_blocking(
                workflow_types, self.request, self.user, **kwargs
            )


# ---------------------------------------------------------------------------
# UI path: start_multiple_workflow_runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_gated_workflow_is_started_and_left_to_the_promoter():
    harness = Harness()

    with harness.patches():
        run_ids = await start_multiple_workflow_runs(
            [CLAIM], harness.request, harness.user
        )

    assert CLAIM in harness.started
    assert run_ids == list(harness.started.values())
    harness.promote.assert_awaited_once_with(str(harness.project.id), 1)
    harness.approve_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_batch_starts_dependencies_before_their_dependents():
    harness = Harness()

    with harness.patches():
        await start_multiple_workflow_runs([CLAIM], harness.request, harness.user)

    order = list(harness.started)
    assert order.index(DOCS) < order.index(EXTRACTION) < order.index(CLAIM)


@pytest.mark.asyncio
async def test_the_batch_joins_a_running_dependency_instead_of_starting_it():
    running = _run(EXTRACTION, WorkflowRunStatus.RUNNING)
    harness = Harness(existing={EXTRACTION: running})

    with harness.patches():
        run_ids = await start_multiple_workflow_runs(
            [CLAIM], harness.request, harness.user
        )

    assert EXTRACTION not in harness.started
    assert str(running.id) in run_ids


# ---------------------------------------------------------------------------
# MCP path: run_multiple_workflows_blocking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocking_path_reports_the_gated_workflow_and_creates_its_run():
    harness = Harness()

    with pytest.raises(WorkflowGateRequiredError) as exc_info:
        await harness.blocking([CLAIM])

    assert exc_info.value.pending_human_approval == [CLAIM]
    assert exc_info.value.pending_web_search == []
    # The run exists so the web UI shows the review banner once it parks.
    assert CLAIM in harness.started
    harness.approve_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocking_path_records_the_approval_when_told_to():
    harness = Harness()

    await harness.blocking([CLAIM], approve_human_steps=True)

    harness.approve_gate.assert_awaited_once()
    args = harness.approve_gate.await_args
    assert args.args[2] == WorkflowGate.REFERENCE_REVIEW
    assert args.kwargs["approved_by_user_id"] == harness.user.id


@pytest.mark.asyncio
async def test_blocking_path_waits_for_every_run_it_started_or_joined():
    running = _run(EXTRACTION, WorkflowRunStatus.RUNNING)
    harness = Harness(
        approved={WorkflowGate.REFERENCE_REVIEW}, existing={EXTRACTION: running}
    )

    _, run_ids = await harness.blocking([CLAIM])

    [waited] = harness.settle.await_args.args
    assert sorted(waited) == sorted([*harness.started.values(), str(running.id)])
    assert sorted(run_ids) == sorted(waited)


@pytest.mark.asyncio
async def test_blocking_path_reports_how_the_ungated_runs_ended_with_the_gate():
    """A failed run is reported as failed, never as a result."""
    harness = Harness()
    harness.settle.side_effect = lambda run_ids: harness.run_statuses.update(
        {harness.started[EXTRACTION]: WorkflowRunStatus.FAILED}
    )

    with pytest.raises(WorkflowGateRequiredError) as exc_info:
        await harness.blocking([CLAIM])

    err = exc_info.value
    assert err.unsuccessful_workflows == {EXTRACTION: WorkflowRunStatus.FAILED}
    assert DOCS in err.completed_workflows
    assert EXTRACTION not in err.completed_workflows
    assert CLAIM not in err.completed_workflows


# ---------------------------------------------------------------------------
# MCP path: web-search consent is a pre-flight check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocking_path_asks_for_web_search_consent_before_creating_any_run():
    harness = Harness()

    with pytest.raises(WorkflowGateRequiredError) as exc_info:
        await harness.blocking([REF_VALIDATION, ABBREVIATIONS])

    err = exc_info.value
    assert err.nothing_started is True
    assert err.pending_web_search == [REF_VALIDATION]
    assert err.pending_human_approval == []
    assert err.retry_workflow_types == [REF_VALIDATION, ABBREVIATIONS]
    assert harness.started == {}
    harness.approve_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocking_path_reports_the_human_gate_alongside_web_consent():
    harness = Harness()

    with pytest.raises(WorkflowGateRequiredError) as exc_info:
        await harness.blocking([CLAIM, REF_VALIDATION])

    err = exc_info.value
    assert err.nothing_started is True
    assert err.pending_web_search == [REF_VALIDATION]
    assert err.pending_human_approval == [CLAIM]
    assert harness.started == {}


@pytest.mark.asyncio
async def test_blocking_path_skips_web_consent_for_a_completed_dependency():
    """A web-search workflow that already completed and is only pulled in as a
    dependency is skipped, so it must not trigger the consent pre-flight."""
    harness = Harness(
        existing={REF_VALIDATION: _run(REF_VALIDATION, WorkflowRunStatus.COMPLETED)}
    )

    with patch(
        f"{BATCH}.resolve_workflow_dependencies",
        return_value=[DOCS, REF_VALIDATION, ABBREVIATIONS],
    ):
        await harness.blocking([ABBREVIATIONS])

    assert ABBREVIATIONS in harness.started
    assert REF_VALIDATION not in harness.started


@pytest.mark.asyncio
async def test_blocking_path_runs_web_search_workflows_once_consented():
    harness = Harness()

    await harness.blocking([REF_VALIDATION, ABBREVIATIONS], approve_web_search=True)

    assert {REF_VALIDATION, ABBREVIATIONS} <= set(harness.started)


@pytest.mark.asyncio
async def test_blocking_path_still_reports_the_claim_gate_after_web_consent():
    """With web consent given, the human gate stays a mid-flight gate: the
    ungated work runs and the claim run waits on its gate."""
    harness = Harness()

    with pytest.raises(WorkflowGateRequiredError) as exc_info:
        await harness.blocking([CLAIM, REF_VALIDATION], approve_web_search=True)

    err = exc_info.value
    assert err.nothing_started is False
    assert err.pending_human_approval == [CLAIM]
    assert err.pending_web_search == []
    assert err.retry_workflow_types == [CLAIM]
    assert {CLAIM, REF_VALIDATION} <= set(harness.started)


# ---------------------------------------------------------------------------
# Approving a gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approving_a_gate_records_it_and_returns_what_the_promoter_released():
    harness = Harness()
    harness.promote.return_value = Promotion(released=["run-1"], queued=["run-1"])

    with harness.patches():
        released = await approve_project_gate(
            harness.project, WorkflowGate.REFERENCE_REVIEW, harness.user
        )

    assert released == ["run-1"]
    harness.approve_gate.assert_awaited_once_with(
        str(harness.project.id),
        1,
        WorkflowGate.REFERENCE_REVIEW,
        approved_by_user_id=harness.user.id,
    )
    harness.promote.assert_awaited_once_with(str(harness.project.id), 1)
