import asyncio
import logging
from typing import List, Optional

from lib.models.workflow_run import WorkflowRunStatus
from lib.services.workflow_runs import get_project_workflow_run_by_type, update_workflow_run_status
from lib.workflows.models import WorkflowCancelledError, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# How often to check dependency/lock status (in seconds)
DEPENDENCY_CHECK_INTERVAL = 5.0


async def wait_for_dependencies(
    workflow_type: WorkflowRunType,
    project_id: str,
    current_workflow_run_id: Optional[str] = None,
) -> None:
    """
    Wait for all dependencies of a project workflow to complete.

    This function handles two types of waiting:
    1. Same-type locking: If current_workflow_run_id is provided, waits for any other
       PENDING/RUNNING instance of the same workflow type to complete first.
    2. Dependency waiting: Waits for required and optional dependencies to complete.

    Args:
        workflow_type: The workflow type to check dependencies for
        project_id: The project ID to check workflow runs for
        current_workflow_run_id: If provided, enables same-type locking (skips self)
    """
    manifest = get_workflow_manifest(workflow_type)
    required_dependencies = manifest.required_dependencies
    optional_dependencies = manifest.optional_dependencies
    all_dependencies = required_dependencies + optional_dependencies

    # Check if we need to wait for anything
    needs_same_type_lock = current_workflow_run_id is not None
    needs_dependency_wait = len(all_dependencies) > 0

    if not needs_same_type_lock and not needs_dependency_wait:
        return

    first_check = True
    while True:
        blocking_reasons: List[str] = []

        # Check same-type lock (wait for previous runs of same workflow)
        if needs_same_type_lock:
            same_type_run = await get_project_workflow_run_by_type(
                project_id, workflow_type
            )
            if (
                same_type_run is not None
                and str(same_type_run.id) != current_workflow_run_id
                and same_type_run.status
                not in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.CANCELLED)
            ):
                blocking_reasons.append(
                    f"previous {workflow_type.value} (run_id {str(same_type_run.id)[:8]}...)"
                )

        # Check dependencies
        if needs_dependency_wait:
            required_pending = await _get_pending_workflow_dependencies(
                project_id, workflow_type, required_dependencies, True,
                current_workflow_run_id=current_workflow_run_id,
            )
            optional_pending = await _get_pending_workflow_dependencies(
                project_id, workflow_type, optional_dependencies, False,
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


async def _get_pending_workflow_dependencies(
    project_id: str,
    workflow_type: WorkflowRunType,
    dependencies: List[WorkflowRunType],
    required: bool,
    current_workflow_run_id: Optional[str] = None,
) -> List[WorkflowRunType]:
    """
    Get the pending workflow dependencies for a project workflow.

    Args:
        project_id: The project ID to check workflow runs for
        workflow_type: The workflow type to check dependencies for
        dependencies: The dependencies to check
        required: Whether the dependencies are required
        current_workflow_run_id: ID of the current run, used to self-cancel when a
            required dependency is cancelled

    Returns:
        A list of pending dependencies

    Raises:
        ValueError: If a required dependency has not been started yet or is not scheduled to run
        WorkflowCancelledError: If a required dependency was cancelled
    """

    pending_dependencies: List[WorkflowRunType] = []

    for dep_type in dependencies:
        dep_run = await get_project_workflow_run_by_type(project_id, dep_type)

        if dep_run is None:
            # Dependency hasn't been started yet or is not scheduled to run

            if required:
                # If the dependency is required, we need to fail the workflow
                raise ValueError(
                    f"{workflow_type} depends on required dependency {dep_type.value} which has not been started yet or is not scheduled to run"
                )
        elif dep_run.status == WorkflowRunStatus.CANCELLED and required:
            # A required dependency was cancelled — cancel this run too (safety net
            # for cases where cascade cancellation hasn't propagated yet)
            if current_workflow_run_id:
                await update_workflow_run_status(
                    current_workflow_run_id, WorkflowRunStatus.CANCELLED
                )
            raise WorkflowCancelledError(
                f"Required dependency {dep_type.value} for {workflow_type} was cancelled"
            )
        elif dep_run.status in (WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING):
            # Dependency is pending or running, wait for it
            pending_dependencies.append(dep_type)

    return pending_dependencies
