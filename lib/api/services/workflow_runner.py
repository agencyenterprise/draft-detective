import asyncio
import logging
import uuid
from typing import List

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from lib.api.models import StartMultipleWorkflowsRequest
from lib.config.env import config as env_config
from lib.models.project import AccessLevel, Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.files import assert_project_has_main_file
from lib.services.projects import get_project_access
from lib.services.users import get_user_decrypted_api_key
from lib.services.workflow_gates import (
    approve_gate,
    get_approved_gates,
    get_effective_gates,
    get_unsatisfied_gates,
    release_runs_awaiting_approval,
)
from lib.services.workflow_runs import (
    create_workflow_run,
    get_project_workflow_run_by_type,
    update_workflow_run_status,
)
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.dependency_resolver import resolve_workflow_dependencies
from lib.workflows.models import WorkflowGate
from lib.workflows.registry import get_config_type, get_workflow_manifest
from lib.workflows.runner import (
    run_workflow_from_config,
    run_workflow_with_dependency_check,
)
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
    """

    def __init__(
        self,
        project_id: str,
        pending_human_approval: List[WorkflowRunType],
        pending_web_search: List[WorkflowRunType],
    ):
        self.project_id = project_id
        self.pending_human_approval = pending_human_approval
        self.pending_web_search = pending_web_search
        parts: List[str] = []
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


async def _prepare_workflow_items(
    workflow_types: List[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    *,
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
    raise_on_pending_gates: bool = False,
) -> tuple[
    Project,
    int,
    List[str],
    List[AutoRunWorkflowItem],
    List[WorkflowRunType],
    List[WorkflowRunType],
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

    workflow_run_ids: List[str] = []
    auto_run_items: List[AutoRunWorkflowItem] = []
    pending_human_triggers: List[WorkflowRunType] = []
    pending_web_search: List[WorkflowRunType] = []
    # Workflows deferred behind the web-search consent gate (the gated
    # workflow itself plus anything downstream of it). Only the MCP path uses
    # this; resolved_workflow_types is in topological order, so a single
    # forward pass is sufficient.
    blocked_set: set[WorkflowRunType] = set()

    revision = project.current_revision
    approved_gates = await get_approved_gates(request.project_id, revision)

    for workflow_type in resolved_workflow_types:
        manifest = get_workflow_manifest(workflow_type)
        existing_run = await get_project_workflow_run_by_type(
            request.project_id, workflow_type, revision=revision
        )

        # Skip if workflow is already completed and not explicitly requested
        # unless the workflow is configured to always run
        if (
            existing_run
            and workflow_type not in workflow_types
            and not manifest.always_run
            and (
                existing_run.status == WorkflowRunStatus.COMPLETED
                # Reference extraction is expensive and runs only once per
                # project, so skip it while it's completed or still in-flight.
                # But allow a re-run when the prior attempt was cancelled or
                # failed — otherwise dependents that need its output get stuck.
                or (
                    existing_run.type == WorkflowRunType.REFERENCE_EXTRACTION
                    and existing_run.status
                    not in (
                        WorkflowRunStatus.CANCELLED,
                        WorkflowRunStatus.FAILED,
                    )
                )
            )
        ):
            logger.info(
                f"Skipping {workflow_type.value} - already exists for project {request.project_id} with status {existing_run.status}"
            )
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

        awaiting_run = (
            existing_run
            if existing_run
            and existing_run.status == WorkflowRunStatus.AWAITING_APPROVAL
            else None
        )

        if unsatisfied_gates:
            if raise_on_pending_gates:
                pending_human_triggers.append(workflow_type)
            if awaiting_run is not None:
                # Already waiting on the same gate; don't create a second copy.
                workflow_run_ids.append(str(awaiting_run.id))
                continue
            awaiting_run_id = await create_workflow_run(
                project_id=request.project_id,
                status=WorkflowRunStatus.AWAITING_APPROVAL,
                type=workflow_type,
                thread_id=str(uuid.uuid4()),
                revision=revision,
            )
            workflow_run_ids.append(awaiting_run_id)
            logger.info(
                f"{workflow_type.value} awaiting approval - waiting on "
                f"{[g.value for g in unsatisfied_gates]}"
            )
            continue

        workflow_config = create_workflow_config(
            project, workflow_type, request.openai_api_key
        )

        if awaiting_run is not None:
            # Its gate was approved while it waited: release this row
            # rather than create a second run of the same type.
            await update_workflow_run_status(
                str(awaiting_run.id), WorkflowRunStatus.PENDING
            )
            thread_id = awaiting_run.langgraph_thread_id
            workflow_run_id = str(awaiting_run.id)
        else:
            # Each run gets a fresh thread id; accumulating workflows carry
            # prior state forward via prior_self_state (read at execution time
            # in the runner) instead of thread reuse.
            thread_id = str(uuid.uuid4())
            workflow_run_id = await create_workflow_run(
                project_id=request.project_id,
                status=WorkflowRunStatus.PENDING,
                type=workflow_type,
                thread_id=thread_id,
                revision=revision,
            )

        workflow_run_ids.append(workflow_run_id)
        auto_run_items.append(
            AutoRunWorkflowItem(
                config=workflow_config,
                thread_id=thread_id,
                workflow_run_id=workflow_run_id,
            )
        )

    return (
        project,
        revision,
        workflow_run_ids,
        auto_run_items,
        pending_human_triggers,
        pending_web_search,
    )


async def start_workflow_run(
    config: WorkflowConfig, user: User, background_tasks: BackgroundTasks
):
    """
    Start a workflow run, by creating a workflow run object, setting it to PENDING and adding a background task to run the workflow with dependency check.

    Args:
        config: The workflow config to run
        user: The user running the workflow
        background_tasks: The background tasks to run the workflow in
    """

    project, _ = await get_project_access(
        config.project_id, user=user, required_level=AccessLevel.WRITE
    )

    _assert_api_key_available(user, config.openai_api_key, config.requires_api_key())

    await assert_project_has_main_file(config.project_id, project.current_revision)

    # Workflows always run against the project's current revision; API/MCP
    # clients don't supply a revision when starting workflows.
    revision = project.current_revision

    # Each run gets a fresh thread id; accumulating workflows carry prior state
    # forward via prior_self_state (read at execution time in the runner) instead
    # of thread reuse.
    thread_id = str(uuid.uuid4())

    unsatisfied_gates = await get_unsatisfied_gates(
        config.project_id, revision, config.type
    )

    # Create new workflow run record
    workflow_run_id = await create_workflow_run(
        project_id=config.project_id,
        status=(
            WorkflowRunStatus.AWAITING_APPROVAL
            if unsatisfied_gates
            else WorkflowRunStatus.PENDING
        ),
        type=config.type,
        thread_id=thread_id,
        revision=revision,
    )

    if unsatisfied_gates:
        logger.info(
            f"{config.type.value} awaiting approval - waiting on "
            f"{[g.value for g in unsatisfied_gates]}"
        )
        return workflow_run_id

    background_tasks.add_task(
        run_workflow_with_dependency_check,
        config=config,
        thread_id=thread_id,
        workflow_run_id=workflow_run_id,
        user=user,
        revision=revision,
    )

    return workflow_run_id


async def start_multiple_workflow_runs(
    workflow_types: List[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    background_tasks: BackgroundTasks,
) -> List[str]:
    """
    Start multiple workflows immediately as PENDING.

    Each workflow will check its dependencies and wait for them to complete
    before starting execution. Workflows run in parallel while still respecting dependencies.

    Args:
        workflow_types: List of workflow types to run
        request: Request containing project_id and optional openai_api_key
        user: User running the workflows
        background_tasks: FastAPI background tasks

    Raises:
        HTTPException: If project_id is missing or project doesn't exist
    """
    (
        _,
        revision,
        workflow_run_ids,
        auto_run_items,
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
    workflow_types: List[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    *,
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
) -> tuple[Project, List[str]]:
    """
    Prepare and run multiple workflows sequentially, blocking until all complete.

    Uses the same dependency resolution and skip logic as start_multiple_workflow_runs
    but runs each workflow in series and awaits the result before starting the next.
    Intended for callers that need the final state synchronously (e.g. MCP tools).

    Args:
        workflow_types: List of workflow types to run (dependencies resolved automatically)
        request: Request containing project_id and optional openai_api_key
        user: User running the workflows
        approve_human_steps: When True, treat any unsatisfied human-trigger
            dependency as approved by the caller and run it inline. When False
            (default), raises WorkflowGateRequiredError so the caller can
            prompt the user to confirm before retrying with approval.
        approve_web_search: When True, treat any workflow with
            manifest.needs_web_search=True as having explicit user consent to
            access the web. When False (default), raises
            WorkflowGateRequiredError so the caller can prompt the user.

    Returns:
        A tuple of (project, list of workflow_run_ids for all created runs)

    Raises:
        WorkflowGateRequiredError: when one or more required consent gates
            (human approval, web-search) are unsatisfied for the resolved
            workflows.
    """
    (
        project,
        revision,
        workflow_run_ids,
        auto_run_items,
        pending_human_triggers,
        pending_web_search,
    ) = await _prepare_workflow_items(
        workflow_types,
        request,
        user,
        approve_human_steps=approve_human_steps,
        approve_web_search=approve_web_search,
        raise_on_pending_gates=True,
    )

    # Run upstream prep (e.g. document_processing, reference_extraction,
    # reference_file_matching) before raising — the user needs those results
    # in order to review the references and decide whether to approve.
    for item in auto_run_items:
        await run_workflow_from_config(
            config=item.config,
            thread_id=item.thread_id,
            workflow_run_id=item.workflow_run_id,
            user=user,
            revision=revision,
        )

    if pending_human_triggers or pending_web_search:
        raise WorkflowGateRequiredError(
            project_id=str(project.id),
            pending_human_approval=pending_human_triggers,
            pending_web_search=pending_web_search,
        )

    return project, workflow_run_ids


async def approve_project_gate(
    project: Project,
    gate: WorkflowGate,
    user: User,
    background_tasks: BackgroundTasks,
) -> List[str]:
    """
    Approve a gate for the project's current revision and schedule every run
    that was awaiting it.

    Idempotent: approving an already-approved gate releases nothing new and
    returns an empty list.

    Returns:
        The IDs of the runs released from AWAITING_APPROVAL and scheduled.
    """
    project_id = str(project.id)
    revision = project.current_revision

    await approve_gate(project_id, revision, gate, approved_by_user_id=user.id)
    released_runs = await release_runs_awaiting_approval(project_id, revision)

    # Configs are rebuilt from the project; the per-request API key (if any)
    # was only ever used to check availability at start time. Resolution at
    # run time falls back to the user's stored key or the server key.
    items = [
        AutoRunWorkflowItem(
            config=create_workflow_config(project, WorkflowRunType(run.type)),
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
    items: List[AutoRunWorkflowItem],
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
