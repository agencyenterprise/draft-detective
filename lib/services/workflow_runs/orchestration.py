import asyncio
import logging
import time

from lib.models.workflow_run import (
    ACTIVE_WORKFLOW_RUN_STATUSES,
    TERMINAL_WORKFLOW_RUN_STATUSES,
    WorkflowRunStatus,
)
from lib.services.workflow_runs.service import (
    get_project_workflow_run_by_type,
    get_workflow_run_status,
    update_workflow_run_status,
)
from lib.workflows.models import (
    DependencyWaitTimeoutError,
    WorkflowCancelledError,
    WorkflowRunType,
)
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# How often to check dependency/lock status (in seconds)
DEPENDENCY_CHECK_INTERVAL = 5.0

# Maximum total time wait_for_dependencies will block before raising
# DependencyWaitTimeoutError. Sized generously so legitimately-long parents
# don't trip it; the reaper is the primary defense against truly stuck runs.
DEPENDENCY_WAIT_TIMEOUT = 2 * 60 * 60  # 2 hours, in seconds


async def wait_for_dependencies(
    workflow_type: WorkflowRunType,
    project_id: str,
    current_workflow_run_id: str | None = None,
    revision: int = 1,
) -> None:
    """
    Wait until a project workflow may start: no same-type run ahead of it and
    no dependency still active.

    This function handles two types of waiting:
    1. Same-type locking: If current_workflow_run_id is provided, waits while
       the run get_project_workflow_run_by_type picks for this type (RUNNING
       first, then the newest PENDING, then AWAITING_APPROVAL) is another
       unfinished run. Two runs of a type never start together, but of two
       waiting PENDING runs the newer one goes first. Workflows with
       independent_runs skip the lock.
    2. Dependency waiting: Waits until no required or optional dependency is
       pending, running or awaiting approval. An optional dependency that never
       started, or that was cancelled or failed, does not hold the run back.

    Each poll also re-reads the current run's own status, so a run cancelled
    (or reaped) while it waits stops waiting instead of starting its graph.

    Args:
        workflow_type: The workflow type to check dependencies for
        project_id: The project ID to check workflow runs for
        current_workflow_run_id: If provided, enables same-type locking (skips
            self) and the own-status check, and is marked CANCELLED when a
            required dependency was cancelled or failed
        revision: The project revision whose runs are checked

    Raises:
        DependencyWaitTimeoutError: If the wait exceeds DEPENDENCY_WAIT_TIMEOUT
        ValueError: If a required dependency has no run on the revision
        WorkflowCancelledError: If a required dependency was cancelled or failed,
            or the current run itself ended while it waited
    """
    manifest = get_workflow_manifest(workflow_type)
    required_dependencies = manifest.required_dependencies
    optional_dependencies = manifest.optional_dependencies
    all_dependencies = required_dependencies + optional_dependencies

    # Check if we need to wait for anything. Independent runs never touch each
    # other's state, so they skip the same-type lock and run side by side.
    needs_same_type_lock = (
        current_workflow_run_id is not None and not manifest.independent_runs
    )
    needs_dependency_wait = len(all_dependencies) > 0

    if not needs_same_type_lock and not needs_dependency_wait:
        return

    first_check = True
    started_at = time.monotonic()
    while True:
        if time.monotonic() - started_at > DEPENDENCY_WAIT_TIMEOUT:
            raise DependencyWaitTimeoutError(
                f"Workflow {workflow_type.value} timed out after "
                f"{DEPENDENCY_WAIT_TIMEOUT}s waiting for dependencies"
            )

        if current_workflow_run_id is not None:
            await _raise_if_run_ended(current_workflow_run_id, workflow_type)

        blocking_reasons: list[str] = []

        # Check same-type lock (wait for previous runs of same workflow)
        if needs_same_type_lock:
            same_type_run = await get_project_workflow_run_by_type(
                project_id, workflow_type, revision=revision
            )
            if (
                same_type_run is not None
                and str(same_type_run.id) != current_workflow_run_id
                and same_type_run.status not in TERMINAL_WORKFLOW_RUN_STATUSES
            ):
                blocking_reasons.append(
                    f"previous {workflow_type.value} (run_id {str(same_type_run.id)[:8]}...)"
                )

        # Check dependencies
        if needs_dependency_wait:
            required_pending = await _get_pending_workflow_dependencies(
                project_id,
                workflow_type,
                required_dependencies,
                True,
                current_workflow_run_id=current_workflow_run_id,
                revision=revision,
            )
            optional_pending = await _get_pending_workflow_dependencies(
                project_id,
                workflow_type,
                optional_dependencies,
                False,
                revision=revision,
            )
            pending_deps = required_pending + optional_pending
            blocking_reasons.extend([dep.value for dep in pending_deps])

        # All clear - proceed
        if not blocking_reasons:
            if not first_check:
                logger.info(
                    f"Workflow {workflow_type.value} - all blockers cleared, proceeding"
                )
            return

        # Log on first check only
        if first_check:
            logger.info(
                f"Workflow {workflow_type.value} waiting for: {blocking_reasons}"
            )
            first_check = False

        await asyncio.sleep(DEPENDENCY_CHECK_INTERVAL)


async def _raise_if_run_ended(
    workflow_run_id: str, workflow_type: WorkflowRunType
) -> None:
    """Raise WorkflowCancelledError once the waiting run is no longer active.

    A user can cancel a PENDING run, and the reaper fails one left PENDING too
    long. Either way the row already holds its final status, so the runner only
    has to stop.
    """
    status = await get_workflow_run_status(workflow_run_id)
    if status in TERMINAL_WORKFLOW_RUN_STATUSES:
        raise WorkflowCancelledError(
            f"Workflow {workflow_type.value} run {workflow_run_id} ended in "
            f"{status.value} while waiting to start"
        )


async def _get_pending_workflow_dependencies(
    project_id: str,
    workflow_type: WorkflowRunType,
    dependencies: list[WorkflowRunType],
    required: bool,
    current_workflow_run_id: str | None = None,
    revision: int = 1,
) -> list[WorkflowRunType]:
    """
    Get the pending workflow dependencies for a project workflow.

    Args:
        project_id: The project ID to check workflow runs for
        workflow_type: The workflow type to check dependencies for
        dependencies: The dependencies to check
        required: Whether the dependencies are required
        current_workflow_run_id: ID of the current run, used to self-cancel when a
            required dependency is cancelled or failed
        revision: The project revision whose runs are checked

    Returns:
        A list of pending dependencies

    Raises:
        ValueError: If a required dependency has not been started yet or is not scheduled to run
        WorkflowCancelledError: If a required dependency was cancelled or failed
    """

    pending_dependencies: list[WorkflowRunType] = []

    for dep_type in dependencies:
        dep_run = await get_project_workflow_run_by_type(
            project_id, dep_type, revision=revision
        )

        if dep_run is None:
            # Dependency hasn't been started yet or is not scheduled to run

            if required:
                # If the dependency is required, we need to fail the workflow
                raise ValueError(
                    f"{workflow_type} depends on required dependency {dep_type.value} which has not been started yet or is not scheduled to run"
                )
        elif (
            dep_run.status in (WorkflowRunStatus.CANCELLED, WorkflowRunStatus.FAILED)
            and required
        ):
            # A required dependency was cancelled or failed — cancel this run too
            # (safety net for cases where cascade hasn't propagated yet). From a
            # dependent's perspective there's no salvageable upstream output, so
            # we mark CANCELLED rather than FAILED.
            if current_workflow_run_id:
                await update_workflow_run_status(
                    current_workflow_run_id, WorkflowRunStatus.CANCELLED
                )
            raise WorkflowCancelledError(
                f"Required dependency {dep_type.value} for {workflow_type} "
                f"ended in {dep_run.status.value}"
            )
        elif dep_run.status in ACTIVE_WORKFLOW_RUN_STATUSES:
            # Dependency is pending, running, or awaiting a gate: wait for it.
            # (A dependent of a gated workflow normally waits alongside it,
            # so the awaiting case here is only a safety net.)
            pending_dependencies.append(dep_type)

    return pending_dependencies


async def wait_for_runs_to_end(run_ids: list[str]) -> None:
    """Wait until every run has a terminal status or no longer exists.

    For runs someone else scheduled. Gives up after DEPENDENCY_WAIT_TIMEOUT
    and leaves the caller to read whatever status the runs then have.
    """
    started_at = time.monotonic()
    pending = list(run_ids)
    while pending:
        statuses = [await get_workflow_run_status(run_id) for run_id in pending]
        pending = [
            run_id
            for run_id, status in zip(pending, statuses, strict=True)
            if status is not None and status not in TERMINAL_WORKFLOW_RUN_STATUSES
        ]
        if not pending:
            return
        if time.monotonic() - started_at > DEPENDENCY_WAIT_TIMEOUT:
            logger.warning(f"Gave up waiting for runs {pending} to end")
            return
        await asyncio.sleep(DEPENDENCY_CHECK_INTERVAL)
