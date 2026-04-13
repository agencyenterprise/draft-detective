import asyncio
import logging
from typing import List

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from lib.api.models import StartMultipleWorkflowsRequest
from lib.config.env import config as env_config
from lib.models.project import AccessLevel, Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.files import assert_project_has_main_file
from lib.services.projects import get_project_access
from lib.services.users import get_user_decrypted_api_key
from lib.services.workflow_runs import (
    create_workflow_run,
    get_project_workflow_run_by_type,
    get_thread_id_for_workflow_run,
)
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.dependency_resolver import resolve_workflow_dependencies
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


logger = logging.getLogger(__name__)


def _assert_api_key_available(user: User, request_key: str | None, requires_key: bool) -> None:
    """Raise HTTP 422 when a workflow needs an API key but none is configured."""
    if not requires_key:
        return
    has_api_key = bool(request_key or get_user_decrypted_api_key(user) or env_config.OPENAI_API_KEY)
    if not has_api_key:
        raise HTTPException(
            status_code=422,
            detail="No OpenAI API key configured. Please add your API key in account settings.",
        )


async def _prepare_workflow_items(
    workflow_types: List[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
) -> tuple[Project, List[str], List[AutoRunWorkflowItem]]:
    """
    Resolve dependencies, apply skip logic, create run records, and build the
    list of items ready for execution.

    Returns a tuple of:
    - project: the resolved Project instance
    - all_workflow_run_ids: IDs of all newly created run records (including
      human-trigger workflows that won't be auto-run)
    - auto_run_items: subset of items that should actually be executed
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
    any_requires_key = any(get_config_type(wt).requires_api_key() for wt in resolved_workflow_types)
    _assert_api_key_available(user, request.openai_api_key, any_requires_key)

    workflow_run_ids: List[str] = []
    auto_run_items: List[AutoRunWorkflowItem] = []

    revision = project.current_revision

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
                # Reference extraction should always run only once per project
                or existing_run.type == WorkflowRunType.REFERENCE_EXTRACTION
            )
        ):
            logger.info(
                f"Skipping {workflow_type.value} - already exists for project {request.project_id} with status {existing_run.status}"
            )
            continue

        workflow_config = create_workflow_config(
            project, workflow_type, request.openai_api_key
        )
        thread_id = get_thread_id_for_workflow_run(existing_run)

        workflow_run_id = await create_workflow_run(
            project_id=request.project_id,
            status=WorkflowRunStatus.PENDING,
            type=workflow_type,
            thread_id=thread_id,
            revision=revision,
        )

        workflow_run_ids.append(workflow_run_id)

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

    return project, workflow_run_ids, auto_run_items


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

    revision = project.current_revision
    # Ensure the config's revision matches the project's current revision so the
    # workflow context (and any state lookups driven by it) target the right
    # revision. Callers of POST /api/workflows/start don't send a revision.
    config.revision = revision
    existing_run = await get_project_workflow_run_by_type(
        config.project_id, config.type, revision=revision
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
        revision=revision,
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
    _, workflow_run_ids, auto_run_items = await _prepare_workflow_items(
        workflow_types, request, user
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


async def run_multiple_workflows_blocking(
    workflow_types: List[WorkflowRunType],
    request: StartMultipleWorkflowsRequest,
    user: User,
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

    Returns:
        A tuple of (project, list of workflow_run_ids for all created runs)
    """
    project, workflow_run_ids, auto_run_items = await _prepare_workflow_items(
        workflow_types, request, user
    )

    for item in auto_run_items:
        await run_workflow_from_config(
            config=item.config,
            thread_id=item.thread_id,
            workflow_run_id=item.workflow_run_id,
            user=user,
        )

    return project, workflow_run_ids


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
