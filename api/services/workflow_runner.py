import asyncio
import logging
from typing import List

from fastapi import BackgroundTasks, HTTPException

from api.models import StartMultipleWorkflowsRequest
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.projects import get_user_project
from lib.services.workflow_runs import (
    create_workflow_run,
    get_project_workflow_run_by_type,
    get_thread_id_for_workflow_run,
)
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.dependency_resolver import resolve_workflow_dependencies
from lib.workflows.registry import get_workflow_manifest
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

    existing_run = await get_project_workflow_run_by_type(
        config.project_id, config.type
    )

    # Reuse thread_id from previous runs to maintain LangGraph checkpoint continuity.
    # This allows workflows to resume from previously computed state (e.g., document
    # chunks already processed) rather than starting from scratch.
    thread_id = get_thread_id_for_workflow_run(existing_run)

    # Create new workflow run record
    workflow_run_id = await create_workflow_run(
        project_id=config.project_id,
        status=WorkflowRunStatus.PENDING,
        type=config.type,
        thread_id=thread_id,
    )

    background_tasks.add_task(
        run_workflow_with_dependency_check,
        config=config,
        thread_id=thread_id,
        workflow_run_id=workflow_run_id,
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
    auto_run_configs: List[WorkflowConfig] = []
    auto_run_thread_ids: List[str] = []
    auto_run_workflow_run_ids: List[str] = []

    for workflow_type in resolved_workflow_types:
        existing_run = await get_project_workflow_run_by_type(
            request.project_id, workflow_type
        )

        # Skip if workflow is already completed and not explicitly requested
        if (
            existing_run
            and existing_run.status == WorkflowRunStatus.COMPLETED
            and workflow_type not in workflow_types
        ):
            logger.info(
                f"Skipping {workflow_type.value} - already completed for project {request.project_id}"
            )
            continue

        # Create workflow-specific config
        workflow_config = create_workflow_config(project, workflow_type, request)

        # Reuse thread_id from previous runs to maintain LangGraph checkpoint continuity
        thread_id = get_thread_id_for_workflow_run(existing_run)

        # Create new workflow run record
        workflow_run_id = await create_workflow_run(
            project_id=request.project_id,
            status=WorkflowRunStatus.PENDING,
            type=workflow_type,
            thread_id=thread_id,
        )

        workflow_run_ids.append(workflow_run_id)

        manifest = get_workflow_manifest(workflow_type)
        if manifest.requires_human_trigger:
            logger.info(
                f"Workflow {workflow_type.value} requires human trigger - skipping auto-run"
            )
            continue

        auto_run_configs.append(workflow_config)
        auto_run_thread_ids.append(thread_id)
        auto_run_workflow_run_ids.append(workflow_run_id)

    if auto_run_configs:
        logger.info(
            f"Auto-running {len(auto_run_configs)} workflows: {[c.type.value for c in auto_run_configs]}"
        )
        background_tasks.add_task(
            _run_multiple_workflows_concurrently,
            workflow_configs=auto_run_configs,
            thread_ids=auto_run_thread_ids,
            workflow_run_ids=auto_run_workflow_run_ids,
            user=user,
        )
    else:
        logger.info(
            "No workflows to auto-run - all require human trigger or already completed"
        )

    return workflow_run_ids


async def _run_multiple_workflows_concurrently(
    workflow_configs: List[WorkflowConfig],
    thread_ids: List[str],
    workflow_run_ids: List[str],
    user: User,
) -> None:
    """
    Run multiple workflows concurrently using asyncio.gather().

    Each workflow will check its dependencies and wait for them to complete
    before starting execution. Workflows run in parallel while still respecting dependencies.

    Args:
        workflow_configs: List of workflow configs to run
        thread_ids: List of thread IDs corresponding to each workflow config
        workflow_run_ids: List of workflow run IDs for same-type locking
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
            config=config,
            thread_id=thread_id,
            workflow_run_id=workflow_run_id,
            user=user,
        )
        for config, thread_id, workflow_run_id in zip(
            workflow_configs, thread_ids, workflow_run_ids
        )
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
