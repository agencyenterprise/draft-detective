"""Planning a batch start: which workflows, with their dependencies, a batch
starts, and which consent gates hold some of them back."""

import logging

from pydantic import BaseModel

from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_start_checks import (
    assert_api_key_available,
    authorized_project,
)
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.gates import (
    approve_gate,
    get_approved_gates,
    get_effective_gates,
)
from lib.services.workflow_runs.service import get_project_workflow_run_by_type
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.dependency_resolver import resolve_workflow_dependencies
from lib.workflows.models import WorkflowGate
from lib.workflows.registry import get_config_type, get_workflow_manifest
from lib.workflows.workflow_types import WorkflowConfig

logger = logging.getLogger(__name__)


class WorkflowGateRequiredError(Exception):
    """Raised when a blocking workflow run hits one or more unsatisfied consent gates.

    Today there are two gate kinds:
      - human approval (manifest.gates, e.g. the reference review)
      - web-search consent (manifest.needs_web_search)

    Each carries the workflow types that triggered it so callers (e.g. the
    MCP tool) can render a useful prompt and ask the user to confirm.

    ``nothing_started`` tells the caller whether this was raised up front,
    before any run record was created (web-search consent is checked before
    anything runs), or mid-flight after the ungated workflows completed.
    ``retry_workflow_types`` is the exact list the caller should pass on the
    retry: the original request when nothing started, otherwise only the
    gated workflows, since anything requested explicitly is run again.
    ``completed_workflows`` and ``unsuccessful_workflows`` report how the
    ungated part of the batch actually ended (the latter maps type to its
    terminal status), so the caller never mistakes a failed run for a result.
    """

    def __init__(
        self,
        project_id: str,
        pending_human_approval: list[WorkflowRunType],
        pending_web_search: list[WorkflowRunType],
        *,
        nothing_started: bool = False,
        retry_workflow_types: list[WorkflowRunType] | None = None,
        completed_workflows: list[WorkflowRunType] | None = None,
        unsuccessful_workflows: dict[WorkflowRunType, WorkflowRunStatus] | None = None,
    ):
        self.project_id = project_id
        self.pending_human_approval = pending_human_approval
        self.pending_web_search = pending_web_search
        self.nothing_started = nothing_started
        self.completed_workflows = list(completed_workflows or [])
        self.unsuccessful_workflows = dict(unsuccessful_workflows or {})
        # De-duplicated in both cases: clients may repeat a type in their
        # request, and the retry list is meant to be a normalized copy.
        self.retry_workflow_types = list(
            dict.fromkeys(
                retry_workflow_types
                if retry_workflow_types is not None
                else pending_human_approval + pending_web_search
            )
        )
        parts: list[str] = []
        if pending_human_approval:
            parts.append(f"human_approval={[w.value for w in pending_human_approval]}")
        if pending_web_search:
            parts.append(f"web_search={[w.value for w in pending_web_search]}")
        super().__init__(
            f"Workflow gates required for project {project_id}: {', '.join(parts)}"
        )


class BatchPlan(BaseModel):
    """What a batch start does, decided before any run is created."""

    project: Project
    revision: int
    # Configs of the workflows to start (or join), dependencies first.
    configs: list[WorkflowConfig] = []
    # RUNNING dependencies the batch waits on instead of starting them again.
    joined_run_ids: list[str] = []
    # Only on the blocking (MCP) path: workflows that wait on a gate, and
    # workflows left out until the user consents to web search.
    pending_human_approval: list[WorkflowRunType] = []
    pending_web_search: list[WorkflowRunType] = []


class _BatchOptions(BaseModel):
    requested: list[WorkflowRunType]
    report_gates: bool
    gate_web_search: bool
    approve_human_steps: bool


def _reused_dependency_run(
    existing_run: WorkflowRun | None,
    workflow_type: WorkflowRunType,
    requested: list[WorkflowRunType],
) -> WorkflowRun | None:
    """The run a batch reuses instead of starting this workflow, if any.

    Applies only to workflows pulled in as dependencies: anything requested
    explicitly, or whose manifest says it always runs, is started (or joins
    the run already waiting). A COMPLETED dependency is skipped, and a
    RUNNING one is joined: its dependents wait for it. Any other dependency
    is started, which joins its waiting run when there is one.
    """
    if existing_run is None or workflow_type in requested:
        return None
    if get_workflow_manifest(workflow_type).always_run:
        return None
    if existing_run.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.RUNNING):
        return existing_run
    return None


async def _raise_if_web_search_consent_missing(
    *,
    requested: list[WorkflowRunType],
    resolved: list[WorkflowRunType],
    project_id: str,
    revision: int,
    approved_gates: set[WorkflowGate],
    approve_human_steps: bool,
) -> None:
    """Pre-flight for the blocking path: if any workflow about to run needs
    web-search consent, stop before a single run record is created.

    Consent to send the document to a search provider is a plain yes/no that
    needs no upstream results, so the caller is asked up front — as the web
    UI does — rather than after every ungated workflow has finished. The
    human-approval gate is reported alongside so the caller can ask both
    questions in one turn, but it is only enforced mid-flight, once the
    references exist for the user to review.
    """
    pending_web_search: list[WorkflowRunType] = []
    for workflow_type in resolved:
        if not get_workflow_manifest(workflow_type).needs_web_search:
            continue
        existing_run = await get_project_workflow_run_by_type(
            project_id, workflow_type, revision=revision
        )
        if _reused_dependency_run(existing_run, workflow_type, requested) is None:
            pending_web_search.append(workflow_type)
    if not pending_web_search:
        return

    pending_human_approval: list[WorkflowRunType] = []
    if not approve_human_steps:
        pending_human_approval = [
            workflow_type
            for workflow_type in resolved
            if any(g not in approved_gates for g in get_effective_gates(workflow_type))
        ]
    raise WorkflowGateRequiredError(
        project_id=project_id,
        pending_human_approval=pending_human_approval,
        pending_web_search=pending_web_search,
        nothing_started=True,
        retry_workflow_types=requested,
    )


async def plan_batch(
    workflow_types: list[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    *,
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
    raise_on_pending_gates: bool = False,
) -> BatchPlan:
    """Resolve the batch's dependencies and decide which workflows it starts.

    ``raise_on_pending_gates`` is the blocking (MCP) path: web-search consent is
    asked up front (WorkflowGateRequiredError before anything starts), and the
    gated workflows are reported in ``pending_human_approval``. Gated workflows
    are started either way: their runs wait on the gate.
    """
    project = await authorized_project(request.project_id, user, model=request.model)
    resolved = resolve_workflow_dependencies(workflow_types)
    assert_api_key_available(
        user,
        request.openai_api_key,
        any(get_config_type(wt).requires_api_key() for wt in resolved),
    )
    plan = BatchPlan(project=project, revision=project.current_revision)
    approved = await get_approved_gates(request.project_id, plan.revision)
    gate_web_search = raise_on_pending_gates and not approve_web_search
    if gate_web_search:
        await _raise_if_web_search_consent_missing(
            requested=workflow_types,
            resolved=resolved,
            project_id=request.project_id,
            revision=plan.revision,
            approved_gates=approved,
            approve_human_steps=approve_human_steps,
        )
    options = _BatchOptions(
        requested=workflow_types,
        report_gates=raise_on_pending_gates,
        gate_web_search=gate_web_search,
        approve_human_steps=approve_human_steps,
    )
    blocked: set[WorkflowRunType] = set()
    for workflow_type in resolved:
        await _plan_workflow(
            plan, workflow_type, request, user, approved, blocked, options
        )
    logger.info(
        f"Batch on project {request.project_id}: {[c.type.value for c in plan.configs]}"
    )
    return plan


async def _plan_workflow(
    plan: BatchPlan,
    workflow_type: WorkflowRunType,
    request: StartMultipleWorkflowsRequest,
    user: User,
    approved: set[WorkflowGate],
    blocked: set[WorkflowRunType],
    options: _BatchOptions,
) -> None:
    """Add one resolved workflow to the plan.

    ``blocked`` collects the workflows left out until web-search consent:
    resolved types come in dependency order, so a single forward pass sees
    every blocked dependency before its dependents.
    """
    manifest = get_workflow_manifest(workflow_type)
    existing = await get_project_workflow_run_by_type(
        request.project_id, workflow_type, revision=plan.revision
    )
    reused = _reused_dependency_run(existing, workflow_type, options.requested)
    if reused is not None:
        logger.info(
            f"Not starting {workflow_type.value}: run {reused.id} is {reused.status.value}"
        )
        if reused.status == WorkflowRunStatus.RUNNING:
            plan.joined_run_ids.append(str(reused.id))
        return
    if any(dep in blocked for dep in manifest.required_dependencies):
        blocked.add(workflow_type)
        return
    if options.gate_web_search and manifest.needs_web_search:
        plan.pending_web_search.append(workflow_type)
        blocked.add(workflow_type)
        return
    unsatisfied = [g for g in get_effective_gates(workflow_type) if g not in approved]
    if unsatisfied and options.approve_human_steps:
        # The caller relayed the user's consent: record it so the approval
        # outlives this request.
        for gate in unsatisfied:
            await approve_gate(
                request.project_id, plan.revision, gate, approved_by_user_id=user.id
            )
            approved.add(gate)
    elif unsatisfied and options.report_gates:
        plan.pending_human_approval.append(workflow_type)
    plan.configs.append(
        create_workflow_config(
            plan.project, workflow_type, request.openai_api_key, request.model
        )
    )
