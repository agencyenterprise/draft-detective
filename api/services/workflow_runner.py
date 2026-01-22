import asyncio
import logging
from typing import List

from fastapi import BackgroundTasks, HTTPException

from api.models import StartMultipleWorkflowsRequest
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.projects import get_user_project
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    get_thread_id_for_workflow_run,
    upsert_workflow_run,
)
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.dependency_resolver import resolve_workflow_dependencies
from lib.workflows.runner import run_workflow_with_dependency_check
from lib.workflows.types import WorkflowConfig

logger = logging.getLogger(__name__)


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

    if config.project_id is None:
        raise HTTPException(status_code=400, detail="Project ID is required")

    # Check if project exists and is owned by the user
    await get_user_project(config.project_id, user)

    workflow_run = await get_project_workflow_run_by_type(
        config.project_id, config.type
    )
    thread_id = get_thread_id_for_workflow_run(workflow_run)

    # Start workflow as PENDING - it will check dependencies and start when ready
    workflow_run_id = await upsert_workflow_run(
        project_id=config.project_id,
        thread_id=thread_id,
        status=WorkflowRunStatus.PENDING,
        type=config.type,
    )

    background_tasks.add_task(
        run_workflow_with_dependency_check,
        config=config,
        thread_id=thread_id,
        user=user,
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
    # Check if project exists and is owned by the user
    project = await get_user_project(request.project_id, user)

    # Resolve all required dependencies in dependency order
    resolved_workflow_types = resolve_workflow_dependencies(workflow_types)

    logger.info(
        f"Resolved to {len(resolved_workflow_types)} workflows (including dependencies): {[w.value for w in resolved_workflow_types]}"
    )

    workflow_run_ids: List[str] = []
    workflow_configs: List[WorkflowConfig] = []
    thread_ids: List[str] = []

    for workflow_type in resolved_workflow_types:
        # We must check if workflow is already completed
        workflow_run = await get_project_workflow_run_by_type(
            request.project_id, workflow_type
        )

        if (
            workflow_run
            and workflow_run.status == WorkflowRunStatus.COMPLETED
            and workflow_run.type not in workflow_types
        ):
            # Skip if workflow is already completed and not in the list of requested workflows
            # If the workflow is in the list of requested workflows, we need to re-run it, regardless of wether it ran already because it might have been re-requested by the user
            logger.info(
                f"Skipping {workflow_type.value} - already completed for project {request.project_id}"
            )
            continue

        # Create workflow-specific config
        workflow_config = create_workflow_config(project, workflow_type, request)

        # Get or create thread_id
        thread_id = get_thread_id_for_workflow_run(workflow_run)

        # Start workflow as PENDING - it will check dependencies and start when ready
        workflow_run_id = await upsert_workflow_run(
            project_id=request.project_id,
            thread_id=thread_id,
            status=WorkflowRunStatus.PENDING,
            type=workflow_type,
        )

        workflow_run_ids.append(workflow_run_id)
        workflow_configs.append(workflow_config)
        thread_ids.append(thread_id)

    # Add a single background task that runs all workflows concurrently
    if workflow_configs:
        logger.info(
            f"Starting {len(workflow_configs)} workflows as PENDING: {[c.type.value for c in workflow_configs]}"
        )
        background_tasks.add_task(
            _run_multiple_workflows_concurrently,
            workflow_configs=workflow_configs,
            thread_ids=thread_ids,
            user=user,
        )
    else:
        logger.info("No workflows to start - all requested workflows already completed")

    return workflow_run_ids


async def _run_multiple_workflows_concurrently(
    workflow_configs: List[WorkflowConfig], thread_ids: List[str], user: User
) -> None:
    """
    Run multiple workflows concurrently using asyncio.gather().

    Each workflow will check its dependencies and wait for them to complete
    before starting execution. Workflows run in parallel while still respecting dependencies.

    Args:
        workflow_configs: List of workflow configs to run
        thread_ids: List of thread IDs corresponding to each workflow config
        user: User running the workflows
    """
    if not workflow_configs:
        return

    logger.info(
        f"Running {len(workflow_configs)} workflows concurrently: {[c.type.value for c in workflow_configs]}"
    )

    # Create tasks for all workflows - they will run in parallel
    tasks = [
        run_workflow_with_dependency_check(
            config=config, thread_id=thread_id, user=user
        )
        for config, thread_id in zip(workflow_configs, thread_ids)
    ]

    # Run all workflows concurrently - each will handle its own dependency waiting
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Log any errors that occurred
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                f"Workflow {workflow_configs[i].type.value} failed: {result}",
                exc_info=True,
            )
