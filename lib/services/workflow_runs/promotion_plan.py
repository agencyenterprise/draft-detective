"""What the promoter should do with a project revision's waiting runs, decided
from the runs and approved gates alone (no I/O, so it is tested directly).

For each waiting run (PENDING or AWAITING_APPROVAL):

- a required dependency whose type last ended CANCELLED or FAILED (or never
  ran) cancels it, and that cancel cascades to its own waiting dependents;
- it is blocked while a required dependency has not COMPLETED, an optional
  dependency is active, or (unless the workflow runs independently) a run of
  its own type is RUNNING;
- an unapproved gate (its own or a required dependency's) parks it in
  AWAITING_APPROVAL, but only once the gate is all that holds it back; any
  other blocker keeps it PENDING;
- otherwise it is ready: PENDING, and its job is queued.

A dependency's state is the type's most relevant run on the revision: RUNNING,
then PENDING, then AWAITING_APPROVAL, then the latest run to end.
"""

import uuid

from pydantic import BaseModel, ConfigDict

from lib.models.workflow_run import (
    ACTIVE_WORKFLOW_RUN_STATUSES,
    WAITING_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
)
from lib.services.workflow_runs.gates import get_effective_gates
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowGate, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

_LOST = (WorkflowRunStatus.CANCELLED, WorkflowRunStatus.FAILED)
_PRIORITY = {
    WorkflowRunStatus.RUNNING: 0,
    WorkflowRunStatus.PENDING: 1,
    WorkflowRunStatus.AWAITING_APPROVAL: 2,
}

Statuses = dict[uuid.UUID, WorkflowRunStatus]


class PromotionPlan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    cancel: list[WorkflowRun] = []
    park: list[WorkflowRun] = []
    release: list[WorkflowRun] = []
    ready: list[WorkflowRun] = []


def plan_promotion(
    runs: list[WorkflowRun], approved: set[WorkflowGate]
) -> PromotionPlan:
    """Decide every waiting run's next step; see the module docstring."""
    statuses: Statuses = {run.id: run.status for run in runs}
    plan = PromotionPlan(cancel=_cascade(runs, statuses))
    by_type = _status_by_type(runs, statuses)
    running = {
        _key(run.type)
        for run in runs
        if statuses[run.id] == WorkflowRunStatus.RUNNING and not run.independent_run
    }
    for run in _waiting(runs, statuses):
        manifest = _manifest(run)
        if manifest is None:
            continue
        blocked = _blocked_by_runs(run, manifest, by_type, running)
        gated = any(g not in approved for g in get_effective_gates(manifest.type))
        _place(plan, run, blocked=blocked, gated=gated)
    return plan


def _place(
    plan: PromotionPlan, run: WorkflowRun, *, blocked: bool, gated: bool
) -> None:
    parked = run.status == WorkflowRunStatus.AWAITING_APPROVAL
    if gated and not blocked:
        if not parked:
            plan.park.append(run)
        return
    if parked:
        plan.release.append(run)
    if not blocked:
        plan.ready.append(run)


def _cascade(runs: list[WorkflowRun], statuses: Statuses) -> list[WorkflowRun]:
    """The waiting runs a lost required dependency cancels, transitively."""
    cancelled: list[WorkflowRun] = []
    while True:
        by_type = _status_by_type(runs, statuses)
        lost = [
            run
            for run in _waiting(runs, statuses)
            if (manifest := _manifest(run)) is not None
            and any(
                by_type.get(_key(dep)) in (*_LOST, None)
                for dep in manifest.required_dependencies
            )
        ]
        if not lost:
            return cancelled
        for run in lost:
            statuses[run.id] = WorkflowRunStatus.CANCELLED
        cancelled.extend(lost)


def _blocked_by_runs(
    run: WorkflowRun,
    manifest: WorkflowManifest,
    by_type: dict[str, WorkflowRunStatus],
    running: set[str],
) -> bool:
    if not run.independent_run and _key(run.type) in running:
        return True
    if any(
        by_type.get(_key(dep)) != WorkflowRunStatus.COMPLETED
        for dep in manifest.required_dependencies
    ):
        return True
    return any(
        by_type.get(_key(dep)) in ACTIVE_WORKFLOW_RUN_STATUSES
        for dep in manifest.optional_dependencies
    )


def _status_by_type(
    runs: list[WorkflowRun], statuses: Statuses
) -> dict[str, WorkflowRunStatus]:
    """Each type's most relevant status (see the module docstring)."""
    ranked = sorted(
        runs,
        key=lambda run: (
            _PRIORITY.get(statuses[run.id], 3),
            -run.created_at.timestamp(),
        ),
    )
    by_type: dict[str, WorkflowRunStatus] = {}
    for run in ranked:
        by_type.setdefault(_key(run.type), statuses[run.id])
    return by_type


def _waiting(runs: list[WorkflowRun], statuses: Statuses) -> list[WorkflowRun]:
    return [run for run in runs if statuses[run.id] in WAITING_WORKFLOW_RUN_STATUSES]


def _manifest(run: WorkflowRun) -> WorkflowManifest | None:
    """The run's manifest; None for a retired type, which is left as it is."""
    return get_workflow_manifest(run.type, raise_exception=False)


def _key(workflow_type: WorkflowRunType | str) -> str:
    """A type as a plain string: rows may hold the enum or its raw value."""
    return (
        workflow_type.value
        if isinstance(workflow_type, WorkflowRunType)
        else workflow_type
    )
