"""Starting workflows: the single and batch starts the API and the MCP tool
use, and gate approval.

Each start creates (or joins) the waiting runs, then schedules the ones it owns
as FastAPI background tasks running ``run_workflow_with_dependency_check``.
Executing a run is ``lib/workflows/runner.py``; the run rows and the waiting
rules are ``lib/services/workflow_runs/``. See docs/workflow-runs.md.
"""

import asyncio
import logging

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from lib.api.models import StartMultipleWorkflowsRequest
from lib.config.env import config as env_config
from lib.config.llm_models import LLMModel
from lib.models.project import AccessLevel, Project
from lib.models.user import User
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.files.service import assert_project_has_main_file
from lib.services.projects.service import get_project_access
from lib.services.users import get_user_decrypted_api_key
from lib.services.workflow_runs.gates import (
    approve_gate,
    get_approved_gates,
    get_effective_gates,
    get_unsatisfied_gates,
    release_runs_awaiting_approval,
)
from lib.services.workflow_runs.orchestration import wait_for_runs_to_end
from lib.services.workflow_runs.service import (
    get_project_workflow_run_by_type,
    get_workflow_run_status,
)
from lib.services.workflow_runs.start import start_or_join_run
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.dependency_resolver import resolve_workflow_dependencies
from lib.workflows.models import WorkflowGate
from lib.workflows.registry import get_config_type, get_workflow_manifest
from lib.workflows.runner import run_workflow_with_dependency_check
from lib.workflows.workflow_types import WorkflowConfig


class AutoRunWorkflowItem(BaseModel):
    """Groups workflow data needed for auto-running a workflow."""

    config: WorkflowConfig
    thread_id: str
    workflow_run_id: str


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


logger = logging.getLogger(__name__)


def _assert_api_key_available(
    user: User, request_key: str | None, requires_key: bool
) -> None:
    """Raise HTTP 422 when a workflow needs an API key but none is configured."""
    if not requires_key:
        return
    has_api_key = bool(
        request_key or get_user_decrypted_api_key(user) or env_config.OPENAI_API_KEY
    )
    if not has_api_key:
        raise HTTPException(
            status_code=422,
            detail="No OpenAI API key configured. Please add your API key in account settings.",
        )


def _assert_model_override_allowed(model: str | None) -> None:
    """Raise HTTP 422 when a request names a model the server will not run.

    The name must carry its provider: agents choose their API key, reasoning
    settings and web-search tool by it, so a bare name would run without them.
    """
    if model is None:
        return
    if not env_config.ALLOW_WORKFLOW_MODEL_OVERRIDE:
        raise HTTPException(
            status_code=422,
            detail="This server does not accept a workflow model override (ALLOW_WORKFLOW_MODEL_OVERRIDE is off).",
        )
    override = LLMModel.from_model_name(model)
    if not override.provider or not override.name:
        raise HTTPException(
            status_code=422,
            detail=f"Model {model!r} must name its provider, e.g. 'openai:gpt-5.6-sol'.",
        )


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


async def _prepare_workflow_items(
    workflow_types: list[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    *,
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
    raise_on_pending_gates: bool = False,
) -> tuple[
    Project,
    int,
    list[str],
    list[AutoRunWorkflowItem],
    list[WorkflowRunType],
    list[WorkflowRunType],
    list[tuple[WorkflowRunType, str]],
]:
    """
    Resolve dependencies, apply skip logic, create run records, and build the
    list of items ready for execution.

    Returns a tuple of:
    - project: the resolved Project instance
    - revision: the project revision this batch targets (always current_revision)
    - all_workflow_run_ids: IDs of all run records this batch owns, including
      runs in AWAITING_APPROVAL that won't be auto-run
    - auto_run_items: subset of items that should actually be executed
    - pending_human_triggers: gated workflows held behind an unapproved gate
      (only populated when raise_on_pending_gates=True)
    - pending_web_search: workflows blocked by missing web-search consent
      (only populated when raise_on_pending_gates=True)
    - joined_runs: (type, run id) of each run the batch joined that someone
      else scheduled (a waiting PENDING run or a RUNNING dependency); the
      batch must not run them, but a caller that blocks must wait for them
    """
    project, _ = await get_project_access(
        request.project_id, user=user, required_level=AccessLevel.WRITE
    )

    await assert_project_has_main_file(request.project_id, project.current_revision)

    resolved_workflow_types = resolve_workflow_dependencies(workflow_types)

    logger.info(
        f"Resolved to {len(resolved_workflow_types)} workflows (including dependencies): {[w.value for w in resolved_workflow_types]}"
    )

    # Workflows that don't use LLMs (requires_api_key() == False) are exempt.
    any_requires_key = any(
        get_config_type(wt).requires_api_key() for wt in resolved_workflow_types
    )
    _assert_api_key_available(user, request.openai_api_key, any_requires_key)
    _assert_model_override_allowed(request.model)

    workflow_run_ids: list[str] = []
    auto_run_items: list[AutoRunWorkflowItem] = []
    pending_human_triggers: list[WorkflowRunType] = []
    pending_web_search: list[WorkflowRunType] = []
    joined_runs: list[tuple[WorkflowRunType, str]] = []
    # Workflows deferred behind the web-search consent gate (the gated
    # workflow itself plus anything downstream of it). Only the MCP path uses
    # this; resolved_workflow_types is in topological order, so a single
    # forward pass is sufficient.
    blocked_set: set[WorkflowRunType] = set()

    revision = project.current_revision
    approved_gates = await get_approved_gates(request.project_id, revision)

    if raise_on_pending_gates and not approve_web_search:
        await _raise_if_web_search_consent_missing(
            requested=workflow_types,
            resolved=resolved_workflow_types,
            project_id=request.project_id,
            revision=revision,
            approved_gates=approved_gates,
            approve_human_steps=approve_human_steps,
        )

    for workflow_type in resolved_workflow_types:
        manifest = get_workflow_manifest(workflow_type)
        existing_run = await get_project_workflow_run_by_type(
            request.project_id, workflow_type, revision=revision
        )

        reused_run = _reused_dependency_run(existing_run, workflow_type, workflow_types)
        if reused_run is not None:
            logger.info(
                f"Not starting {workflow_type.value} - its run {reused_run.id} for "
                f"project {request.project_id} is {reused_run.status.value}"
            )
            if reused_run.status == WorkflowRunStatus.RUNNING:
                workflow_run_ids.append(str(reused_run.id))
                joined_runs.append((workflow_type, str(reused_run.id)))
            continue

        # If any required dep is deferred behind the web-search consent gate,
        # this workflow is downstream and must wait for the post-consent
        # retry. Don't create a record either — the next call will.
        if any(dep in blocked_set for dep in manifest.required_dependencies):
            logger.info(
                f"Deferring {workflow_type.value} - depends on a workflow blocked by a consent gate"
            )
            blocked_set.add(workflow_type)
            continue

        # Web-search consent gate. Only enforced on the blocking/MCP path
        # (raise_on_pending_gates=True); the UI path collects consent in the
        # frontend, so we don't gate it again at the backend there.
        if (
            manifest.needs_web_search
            and not approve_web_search
            and raise_on_pending_gates
        ):
            pending_web_search.append(workflow_type)
            blocked_set.add(workflow_type)
            continue

        # Approval gates (own and inherited from required dependencies).
        unsatisfied_gates = [
            gate
            for gate in get_effective_gates(workflow_type)
            if gate not in approved_gates
        ]
        if unsatisfied_gates and approve_human_steps:
            # The caller relayed the user's consent: record it so the approval
            # outlives this request, then proceed as if it had been there.
            for gate in unsatisfied_gates:
                await approve_gate(
                    request.project_id, revision, gate, approved_by_user_id=user.id
                )
                approved_gates.add(gate)
            unsatisfied_gates = []

        start = await start_or_join_run(
            request.project_id,
            workflow_type,
            revision,
            model=request.model,
            gated=bool(unsatisfied_gates),
        )
        workflow_run_ids.append(start.run_id)
        if start.status == WorkflowRunStatus.AWAITING_APPROVAL:
            if raise_on_pending_gates:
                pending_human_triggers.append(workflow_type)
            logger.info(
                f"{workflow_type.value} awaiting approval - waiting on "
                f"{[g.value for g in unsatisfied_gates]}"
            )
            continue
        if not start.schedule:
            joined_runs.append((workflow_type, start.run_id))
            continue

        auto_run_items.append(
            AutoRunWorkflowItem(
                config=create_workflow_config(
                    project, workflow_type, request.openai_api_key, start.model
                ),
                thread_id=start.thread_id,
                workflow_run_id=start.run_id,
            )
        )

    return (
        project,
        revision,
        workflow_run_ids,
        auto_run_items,
        pending_human_triggers,
        pending_web_search,
        joined_runs,
    )


async def start_workflow_run(
    config: WorkflowConfig, user: User, background_tasks: BackgroundTasks
):
    """
    Start a workflow run: create a PENDING run and add a background task that
    runs it with the dependency check. A workflow held behind an unapproved
    gate instead gets an AWAITING_APPROVAL run and no task.

    When a run of the type is already waiting on this revision, the start
    joins it and creates nothing: it schedules it only when it releases it
    from AWAITING_APPROVAL (its gate was approved meanwhile), and the run keeps
    the model its row records. So a start while one run is RUNNING queues one
    run behind it, and later starts join that one. Independent-run workflows
    always get a new run.

    Args:
        config: The workflow config to run
        user: The user running the workflow
        background_tasks: The background tasks to run the workflow in

    Returns:
        The ID of the run that serves this start
    """

    project, _ = await get_project_access(
        config.project_id, user=user, required_level=AccessLevel.WRITE
    )

    _assert_api_key_available(user, config.openai_api_key, config.requires_api_key())
    _assert_model_override_allowed(config.model)

    await assert_project_has_main_file(config.project_id, project.current_revision)

    # Workflows always run against the project's current revision; API/MCP
    # clients don't supply a revision when starting workflows.
    revision = project.current_revision

    unsatisfied_gates = await get_unsatisfied_gates(
        config.project_id, revision, config.type
    )
    start = await start_or_join_run(
        config.project_id,
        config.type,
        revision,
        model=config.model,
        gated=bool(unsatisfied_gates),
    )
    if start.status == WorkflowRunStatus.AWAITING_APPROVAL:
        logger.info(
            f"{config.type.value} awaiting approval - waiting on "
            f"{[g.value for g in unsatisfied_gates]}"
        )

    if start.schedule:
        background_tasks.add_task(
            run_workflow_with_dependency_check,
            config=config.model_copy(update={"model": start.model}),
            thread_id=start.thread_id,
            workflow_run_id=start.run_id,
            user=user,
            revision=revision,
        )

    return start.run_id


async def start_multiple_workflow_runs(
    workflow_types: list[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    background_tasks: BackgroundTasks,
) -> list[str]:
    """
    Start multiple workflows and their dependencies in the background.

    Each workflow creates or joins its waiting run (see start_workflow_run):
    the batch schedules the runs it created PENDING or released from
    AWAITING_APPROVAL, and leaves a joined PENDING run to whoever scheduled
    it. A dependency that _reused_dependency_run picks (COMPLETED or RUNNING)
    gets no new run.
    Each scheduled workflow waits for its own dependencies, so they run in
    parallel while still respecting dependencies.

    Args:
        workflow_types: List of workflow types to run
        request: Request containing project_id and optional openai_api_key
        user: User running the workflows
        background_tasks: FastAPI background tasks

    Returns:
        The IDs of every run this batch owns, including those awaiting approval

    Raises:
        HTTPException: 404 if the project doesn't exist, 403 without write
            access, 422 if it has no main file, no API key is available or the
            model override is not allowed
    """
    (
        _,
        revision,
        workflow_run_ids,
        auto_run_items,
        _,
        _,
        _,
    ) = await _prepare_workflow_items(workflow_types, request, user)

    if auto_run_items:
        logger.info(
            f"Auto-running {len(auto_run_items)} workflows: {[item.config.type.value for item in auto_run_items]}"
        )
        background_tasks.add_task(
            _run_multiple_workflows_concurrently,
            items=auto_run_items,
            user=user,
            revision=revision,
        )
    else:
        logger.info(
            "No workflows to auto-run - all require human trigger or already completed"
        )

    return workflow_run_ids


async def run_multiple_workflows_blocking(
    workflow_types: list[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    *,
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
) -> tuple[Project, list[str]]:
    """
    Prepare and run multiple workflows, blocking until all complete.

    Uses the same dependency resolution, skip logic and concurrent execution as
    start_multiple_workflow_runs, but awaits the batch instead of handing it to
    a background task. Intended for callers that need the final state
    synchronously (e.g. MCP tools). Runs the batch joined (scheduled by
    someone else) are not run here, but the call waits for them to end too (up
    to DEPENDENCY_WAIT_TIMEOUT, after which it returns anyway). A
    workflow that fails is logged and left FAILED on its run record; it does
    not abort the rest of the batch or this call.

    Args:
        workflow_types: List of workflow types to run (dependencies resolved automatically)
        request: Request containing project_id and optional openai_api_key
        user: User running the workflows
        approve_human_steps: When True, record every unsatisfied approval gate
            of the resolved workflows as approved by the user, for the
            project's revision, and run the gated workflows inline. When False
            (default), raises WorkflowGateRequiredError so the caller can
            prompt the user to confirm before retrying with approval.
        approve_web_search: When True, treat any workflow with
            manifest.needs_web_search=True as having explicit user consent to
            access the web. When False (default), raises
            WorkflowGateRequiredError so the caller can prompt the user.

    Returns:
        A tuple of (project, the IDs of every run this batch owns: new runs,
        joined waiting runs and joined RUNNING dependencies)

    Raises:
        WorkflowGateRequiredError: when one or more required consent gates
            (human approval, web-search) are unsatisfied for the resolved
            workflows.
        HTTPException: as start_multiple_workflow_runs does
    """
    (
        project,
        revision,
        workflow_run_ids,
        auto_run_items,
        pending_human_triggers,
        pending_web_search,
        joined_runs,
    ) = await _prepare_workflow_items(
        workflow_types,
        request,
        user,
        approve_human_steps=approve_human_steps,
        approve_web_search=approve_web_search,
        raise_on_pending_gates=True,
    )

    # Run everything that is ready — including upstream prep such as
    # document_processing, reference_extraction and reference_file_matching —
    # before raising: the user needs those results in order to review the
    # references and decide whether to approve. Items run concurrently, each
    # waiting on its own dependencies, exactly as on the UI path.
    await _run_multiple_workflows_concurrently(
        items=auto_run_items, user=user, revision=revision
    )
    # Runs the batch joined are part of this request too: return only once
    # they have ended.
    await wait_for_runs_to_end([run_id for _, run_id in joined_runs])

    if pending_human_triggers or pending_web_search:
        completed, unsuccessful = await _batch_outcomes(
            [(item.config.type, item.workflow_run_id) for item in auto_run_items]
            + joined_runs
        )
        raise WorkflowGateRequiredError(
            project_id=str(project.id),
            pending_human_approval=pending_human_triggers,
            pending_web_search=pending_web_search,
            completed_workflows=completed,
            unsuccessful_workflows=unsuccessful,
        )

    return project, workflow_run_ids


async def _batch_outcomes(
    runs: list[tuple[WorkflowRunType, str]],
) -> tuple[list[WorkflowRunType], dict[WorkflowRunType, WorkflowRunStatus]]:
    """Split a finished batch into completed types and type → terminal status
    for the rest. The concurrent runner absorbs per-item failures, so this is
    read back from the run records rather than inferred."""
    completed: list[WorkflowRunType] = []
    unsuccessful: dict[WorkflowRunType, WorkflowRunStatus] = {}
    for workflow_type, run_id in runs:
        status = await get_workflow_run_status(run_id)
        if status == WorkflowRunStatus.COMPLETED:
            completed.append(workflow_type)
        else:
            unsuccessful[workflow_type] = status or WorkflowRunStatus.FAILED
    return completed, unsuccessful


async def approve_project_gate(
    project: Project,
    gate: WorkflowGate,
    user: User,
    background_tasks: BackgroundTasks,
) -> list[str]:
    """
    Approve a gate for the project's current revision and schedule every run
    that was awaiting it.

    Idempotent: approving an already-approved gate records nothing new. It
    still releases any run whose gates are now all approved, such as one left
    waiting when the MCP path recorded the approval for other workflows, and
    returns an empty list when there is none.

    Returns:
        The IDs of the runs released from AWAITING_APPROVAL and scheduled.
    """
    project_id = str(project.id)
    revision = project.current_revision

    await approve_gate(project_id, revision, gate, approved_by_user_id=user.id)
    released_runs = await release_runs_awaiting_approval(project_id, revision)

    # Configs are rebuilt from the project; the per-request API key (if any)
    # was only ever used to check availability at start time. Resolution at
    # run time falls back to the user's stored key or the server key. The model
    # override is the one exception: it is kept on the run for exactly this.
    items = [
        AutoRunWorkflowItem(
            config=create_workflow_config(
                project, WorkflowRunType(run.type), model=run.model
            ),
            thread_id=run.langgraph_thread_id,
            workflow_run_id=str(run.id),
        )
        for run in released_runs
    ]

    if items:
        background_tasks.add_task(
            _run_multiple_workflows_concurrently,
            items=items,
            user=user,
            revision=revision,
        )

    return [item.workflow_run_id for item in items]


async def _run_multiple_workflows_concurrently(
    items: list[AutoRunWorkflowItem],
    user: User,
    revision: int,
) -> None:
    """
    Run multiple workflows concurrently using asyncio.gather().

    Each workflow will check its dependencies and wait for them to complete
    before starting execution. Workflows run in parallel while still respecting dependencies.

    Args:
        items: List of workflow items containing config, thread_id, and workflow_run_id
        user: User running the workflows
        revision: The project revision this batch targets
    """
    if not items:
        return

    logger.info(
        f"Running {len(items)} workflows concurrently: {[item.config.type.value for item in items]}"
    )

    # Create tasks for all workflows - they will run in parallel
    tasks = [
        run_workflow_with_dependency_check(
            config=item.config,
            thread_id=item.thread_id,
            workflow_run_id=item.workflow_run_id,
            user=user,
            revision=revision,
        )
        for item in items
    ]

    # Run all workflows concurrently - each will handle its own dependency waiting
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Log any errors that occurred
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                f"Workflow {items[i].config.type.value} failed: {result}",
                exc_info=True,
            )
