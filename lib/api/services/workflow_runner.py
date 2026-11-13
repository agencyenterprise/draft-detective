"""Starting workflows: the single and batch starts the API and the MCP tool
use, and gate approval.

Every start creates (or joins) the waiting runs, then calls
``promote_ready_runs``, which queues whichever are ready. Nothing runs here.
"""

import logging
from collections.abc import Awaitable, Callable

from lib.api.models import StartMultipleWorkflowsRequest
from lib.api.services.workflow_batch import WorkflowGateRequiredError, plan_batch
from lib.api.services.workflow_start_checks import (
    assert_api_key_available,
    authorized_project,
)
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.gates import approve_gate
from lib.services.workflow_runs.promoter import promote_ready_runs
from lib.services.workflow_runs.service import get_workflow_run_status
from lib.services.workflow_runs.settle import wait_for_runs_to_settle
from lib.services.workflow_runs.start import start_or_join_run
from lib.workflows.models import WorkflowGate
from lib.workflows.workflow_types import WorkflowConfig

logger = logging.getLogger(__name__)

# Called with a run's id right after a start creates it, before it can be
# queued (the Review Assistant records its request on the run there).
OnRunCreated = Callable[[str], Awaitable[None]]


async def _start_runs(
    configs: list[WorkflowConfig],
    revision: int,
    user: User,
    on_created: OnRunCreated | None = None,
) -> list[str]:
    """Create or join a waiting run per config, then promote, which queues
    whichever of them are ready. Returns the run ids, in config order."""
    run_ids: list[str] = []
    for config in configs:
        start = await start_or_join_run(
            config, config.type, revision, started_by=user.id
        )
        if start.created and on_created is not None:
            await on_created(start.run_id)
        run_ids.append(start.run_id)
    if configs:
        await promote_ready_runs(configs[0].project_id, revision)
    return run_ids


async def start_workflow_run(
    config: WorkflowConfig, user: User, on_created: OnRunCreated | None = None
) -> str:
    """Start one workflow on the project's current revision.

    Creates the PENDING run, or joins the run of the type already waiting (it
    keeps the config and model it was created with); independent-run workflows
    always get a new run. Dependencies are not started: the run waits for
    whatever runs of them exist, and is cancelled when a required one last
    ended CANCELLED or FAILED or never ran. Returns the id of the run that
    serves this start.
    """
    project = await authorized_project(config.project_id, user, model=config.model)
    assert_api_key_available(user, config.openai_api_key, config.requires_api_key())
    [run_id] = await _start_runs([config], project.current_revision, user, on_created)
    return run_id


async def start_multiple_workflow_runs(
    workflow_types: list[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
) -> list[str]:
    """Start workflows and their dependencies on the project's current revision.

    A dependency pulled in that already COMPLETED is not run again, and one that
    is RUNNING is waited on (see ``_reused_dependency_run``). Everything else
    gets a run, or joins the waiting one, and the promoter runs each as soon as
    its dependencies allow. Returns the ids of every run the batch owns,
    including those that will wait on a gate and RUNNING dependencies it joined.
    """
    plan = await plan_batch(workflow_types, request, user)
    run_ids = await _start_runs(plan.configs, plan.revision, user)
    return run_ids + plan.joined_run_ids


async def run_multiple_workflows_blocking(
    workflow_types: list[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
    *,
    approve_human_steps: bool = False,
    approve_web_search: bool = False,
) -> tuple[Project, list[str]]:
    """Start a batch as ``start_multiple_workflow_runs`` does, then wait until
    every run in it has ended or waits on a gate.

    Args:
        approve_human_steps: When True, record every unsatisfied approval gate
            of the resolved workflows as approved by the user, for the
            project's revision. When False (default), the gated workflows wait
            on their gate and WorkflowGateRequiredError is raised once the rest
            of the batch has settled, so the caller can ask the user.
        approve_web_search: When True, the user consents to the workflows that
            search the web. When False (default), WorkflowGateRequiredError is
            raised before anything starts if the batch includes one.

    Returns:
        The project and the ids of every run the batch owns.

    Raises:
        WorkflowGateRequiredError: when a consent gate is unsatisfied.
        HTTPException: as start_multiple_workflow_runs does
    """
    plan = await plan_batch(
        workflow_types,
        request,
        user,
        approve_human_steps=approve_human_steps,
        approve_web_search=approve_web_search,
        raise_on_pending_gates=True,
    )
    run_ids = await _start_runs(plan.configs, plan.revision, user)
    await wait_for_runs_to_settle(run_ids + plan.joined_run_ids)

    if plan.pending_human_approval or plan.pending_web_search:
        gated = set(plan.pending_human_approval)
        completed, unsuccessful = await _batch_outcomes(
            [
                (config.type, run_id)
                for config, run_id in zip(plan.configs, run_ids, strict=True)
                if config.type not in gated
            ]
        )
        raise WorkflowGateRequiredError(
            project_id=str(plan.project.id),
            pending_human_approval=plan.pending_human_approval,
            pending_web_search=plan.pending_web_search,
            completed_workflows=completed,
            unsuccessful_workflows=unsuccessful,
        )
    return plan.project, run_ids + plan.joined_run_ids


async def _batch_outcomes(
    runs: list[tuple[WorkflowRunType, str]],
) -> tuple[list[WorkflowRunType], dict[WorkflowRunType, WorkflowRunStatus]]:
    """Split a settled batch into completed types and type → status for the rest."""
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
    project: Project, gate: WorkflowGate, user: User
) -> list[str]:
    """Approve a gate for the project's current revision, then promote.

    Idempotent: approving an already-approved gate records nothing new. Returns
    the ids of the runs the approval released from AWAITING_APPROVAL.
    """
    project_id = str(project.id)
    revision = project.current_revision
    await approve_gate(project_id, revision, gate, approved_by_user_id=user.id)
    promotion = await promote_ready_runs(project_id, revision)
    return promotion.released
