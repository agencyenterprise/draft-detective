import asyncio
import logging
from typing import List

from lib.models.workflow_run import WorkflowRunStatus
from lib.services.workflow_runs import get_project_workflow_run_by_type
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# How often to check dependency status (in seconds)
# Workflows that have running dependencies will check if they can start every DEPENDENCY_CHECK_INTERVAL seconds
DEPENDENCY_CHECK_INTERVAL = 10.0


async def wait_for_dependencies(
    workflow_type: WorkflowRunType, project_id: str
) -> None:
    """
    Wait for all dependencies of a project workflow to complete.

    Args:
        workflow_type: The workflow type to check dependencies for
        project_id: The project ID to check workflow runs for
    """

    manifest = get_workflow_manifest(workflow_type)
    required_dependencies = manifest.required_dependencies
    optional_dependencies = manifest.optional_dependencies
    all_dependencies = required_dependencies + optional_dependencies

    if not all_dependencies:
        return

    logger.info(
        f"Workflow {workflow_type.value} waiting for dependencies: required={required_dependencies}, optional={optional_dependencies}"
    )

    while True:
        required_pending_dependencies = await _get_pending_workflow_dependencies(
            project_id, workflow_type, required_dependencies, True
        )
        optional_pending_dependencies = await _get_pending_workflow_dependencies(
            project_id, workflow_type, optional_dependencies, False
        )

        pending_dependencies: List[WorkflowRunType] = (
            required_pending_dependencies + optional_pending_dependencies
        )

        if not pending_dependencies:
            logger.info(
                f"All dependencies for {workflow_type.value} are completed, proceeding"
            )
            break

        logger.info(
            f"Workflow {workflow_type.value} still waiting for: {[d.value for d in pending_dependencies]}"
        )
        await asyncio.sleep(DEPENDENCY_CHECK_INTERVAL)


async def _get_pending_workflow_dependencies(
    project_id: str,
    workflow_type: WorkflowRunType,
    dependencies: List[WorkflowRunType],
    required: bool,
) -> List[WorkflowRunType]:
    """
    Get the pending workflow dependencies for a project workflow.

    Args:
        project_id: The project ID to check workflow runs for
        workflow_type: The workflow type to check dependencies for
        dependencies: The dependencies to check
        required: Whether the dependencies are required

    Returns:
        A list of pending dependencies

    Raises:
        ValueError: If a required dependency has not been started yet or is not scheduled to run
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
        elif (
            dep_run.status == WorkflowRunStatus.PENDING
            or dep_run.status == WorkflowRunStatus.RUNNING
        ):
            # Dependency is pending or running, wait for it
            pending_dependencies.append(dep_type)

    return pending_dependencies
