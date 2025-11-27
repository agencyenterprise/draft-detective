import logging
import uuid

from lib.models.workflow_run import WorkflowRunStatus
from lib.services.file import FileDocument
from lib.services.workflow_runs import upsert_workflow_run
from lib.workflows.claim_substantiation.runner import run_claim_substantiator
from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig

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
            thread_id=thread_id, project_id=project_id, status=WorkflowRunStatus.RUNNING
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
        )

        logger.info(
            f"Background workflow completed for project {project_id} and thread {thread_id}"
        )

    except Exception as e:
        logger.error(f"Error in background workflow: {str(e)}", exc_info=True)
