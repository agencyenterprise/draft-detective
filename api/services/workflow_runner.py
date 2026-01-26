import asyncio
import logging
from typing import List

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.models import StartMultipleWorkflowsRequest
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
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


class AutoRunWorkflowItem(BaseModel):
    """Groups workflow data needed for auto-running a workflow."""

    config: WorkflowConfig
    thread_id: str
    workflow_run_id: str


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
    auto_run_items: List[AutoRunWorkflowItem] = []

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

        auto_run_items.append(
            AutoRunWorkflowItem(
                config=workflow_config,
                thread_id=thread_id,
                workflow_run_id=workflow_run_id,
            )
        )

    if auto_run_items:
        logger.info(
            f"Auto-running {len(auto_run_items)} workflows: {[item.config.type.value for item in auto_run_items]}"
        )
        background_tasks.add_task(
            _run_multiple_workflows_concurrently,
            items=auto_run_items,
            user=user,
        )
    else:
        logger.info(
            "No workflows to auto-run - all require human trigger or already completed"
        )

    return workflow_run_ids


async def resume_workflow_run(
    workflow_run: WorkflowRun,
    config: WorkflowConfig,
    user: User,
    background_tasks: BackgroundTasks,
) -> str:
    """
    Resume an existing workflow run by scheduling it to continue.

    Unlike start_workflow_run, this doesn't create a new run record -
    it continues an existing one using its thread_id.

    Args:
        workflow_run: The existing workflow run to resume
        config: The workflow config for this run
        user: The user running the workflow
        background_tasks: FastAPI background tasks

    Returns:
        The workflow run ID
    """
    thread_id = get_thread_id_for_workflow_run(workflow_run)

    background_tasks.add_task(
        run_workflow_with_dependency_check,
        config=config,
        thread_id=thread_id,
        workflow_run_id=str(workflow_run.id),
        user=user,
    )

    return str(workflow_run.id)


async def _run_multiple_workflows_concurrently(
    items: List[AutoRunWorkflowItem],
    user: User,
) -> None:
    """
    Run multiple workflows concurrently using asyncio.gather().

    Each workflow will check its dependencies and wait for them to complete
    before starting execution. Workflows run in parallel while still respecting dependencies.

    Args:
        items: List of workflow items containing config, thread_id, and workflow_run_id
        user: User running the workflows
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
