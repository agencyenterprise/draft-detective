"""
Document analysis endpoints
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from api.dependencies import build_config_from_form
from api.models import StartWorkflowResponse
from api.services.workflow_runner import start_multiple_workflow_runs
from api.upload import save_uploaded_files_to_db
from lib.models.file import FileRole
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunType
from lib.services.projects import create_project
from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/api/start-analysis", response_model=StartWorkflowResponse)
async def start_analysis(
    background_tasks: BackgroundTasks,
    main_document: UploadFile = File(...),
    supporting_documents: Optional[list[UploadFile]] = File(default=None),
    config: SubstantiationWorkflowConfig = Depends(build_config_from_form),
    current_user: User = Depends(get_current_user),
):
    """
    Create a project and immediately start analysis workflows.

    This endpoint:
    1. Creates a project for the analysis
    2. Saves uploaded files to database with file metadata
    3. Creates file document references (without markdown conversion)
    4. Returns immediately with project_id
    5. Starts the analysis workflows in the background (markdown conversion happens here)

    The client can poll /api/project/{project_id} to check progress.

    Args:
        background_tasks: FastAPI background tasks
        main_document: The main document to analyze for claims
        supporting_documents: Optional supporting documents for substantiation
        config: Workflow configuration built from form fields

    Returns:
        project_id to track the analysis
    """
    try:
        # Create project first
        project = await create_project(
            title=main_document.filename or "Untitled",
            user=current_user,
            publication_date=(
                date.fromisoformat(config.publication_date)
                if config.publication_date
                else None
            ),
            domain=config.domain,
            target_audience=config.target_audience,
        )

        logger.info(f"Created project {project.id}")
        config.project_id = str(project.id)

        # Save files to database
        logger.info("Saving uploaded files to database...")
        all_files = [main_document] + (supporting_documents or [])
        roles = [FileRole.MAIN] + [FileRole.SUPPORT] * len(supporting_documents or [])

        file_records = await save_uploaded_files_to_db(
            uploaded_files=all_files,
            project_id=project.id,
            user_id=current_user.id,
            roles=roles,
        )
        logger.info(f"Saved {len(file_records)} files to database")

        # Determine which workflows to run
        # Default to claim substantiation if no workflow_types specified
        workflow_types = config.workflow_types or [WorkflowRunType.CLAIM_SUBSTANTIATION]

        logger.info(
            f"Starting workflows: {[wt.value for wt in workflow_types]} for project {project.id}"
        )

        await start_multiple_workflow_runs(
            workflow_types=workflow_types,
            base_config=config,
            user=current_user,
            background_tasks=background_tasks,
        )

        return StartWorkflowResponse(
            project_id=str(project.id),
            message="Analysis started. Track progress by polling the project endpoint `/api/project/{project_id}`.",
        )

    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error starting analysis: {str(e)}"
        )
