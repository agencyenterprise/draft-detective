import logging
import uuid

from fastapi import BackgroundTasks, HTTPException

from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.file import FileDocument
from lib.services.projects import get_user_project_detailed
from lib.services.workflow_runs import (
    get_project_workflow_run_by_type,
    upsert_workflow_run,
)
from lib.workflows.claim_substantiation.runner import run_claim_substantiator
from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig
from lib.workflows.models import BaseWorkflowConfig, WorkflowRunType
from lib.workflows.runner import run_workflow_from_config

logger = logging.getLogger(__name__)


async def run_workflow_background(
    project_id: str,
    main_file: FileDocument,
    supporting_files: list[FileDocument] | None,
    config: SubstantiationWorkflowConfig,
) -> None:
    """
    Background task to run the claim substantiation workflow.

    Updates workflow status from PENDING -> RUNNING -> COMPLETED.
    """
    try:
        thread_id = str(uuid.uuid4())
        config.session_id = thread_id

        logger.info(
            f"Starting background workflow execution for project {project_id} and thread {thread_id}"
        )

        await upsert_workflow_run(
            thread_id=thread_id,
            project_id=project_id,
            status=WorkflowRunStatus.RUNNING,
            type=WorkflowRunType.CLAIM_SUBSTANTIATION,
        )

        await run_claim_substantiator(
            project_id=project_id,
            thread_id=thread_id,
            file=main_file,
            supporting_files=supporting_files,
            config=config,
        )

        await upsert_workflow_run(
            thread_id=thread_id,
            project_id=project_id,
            status=WorkflowRunStatus.COMPLETED,
            type=WorkflowRunType.CLAIM_SUBSTANTIATION,
        )

        logger.info(
            f"Background workflow completed for project {project_id} and thread {thread_id}"
        )

    except Exception as e:
        logger.error(f"Error in background workflow: {str(e)}", exc_info=True)


async def start_workflow_run(
    config: BaseWorkflowConfig, user: User, background_tasks: BackgroundTasks
):
    if not config.project_id:
        raise HTTPException(status_code=400, detail="Project ID is required")

    # Check if project exists and is owned by the user
    await get_user_project_detailed(config.project_id, user)

    workflow_run = await get_project_workflow_run_by_type(
        config.project_id, config.type
    )

    if workflow_run is not None:
        thread_id = workflow_run.langgraph_thread_id
    else:
        thread_id = str(uuid.uuid4())

    workflow_run_id = await upsert_workflow_run(
        project_id=config.project_id,
        thread_id=thread_id,
        status=WorkflowRunStatus.RUNNING,
        type=config.type,
    )

    background_tasks.add_task(
        run_workflow_from_config,
        config=config,
        thread_id=thread_id,
    )

    return workflow_run_id
