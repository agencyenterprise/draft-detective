"""
Document analysis endpoints
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from api.dependencies import build_config_from_form
from api.models import (
    AnalysisFormConfig,
    StartMultipleWorkflowsRequest,
    StartWorkflowResponse,
)
from lib.services.preflight.models import PreflightRequest, PreflightResult
from lib.services.preflight.service import preflight_service
from api.services.workflow_runner import start_multiple_workflow_runs
from api.upload import save_uploaded_files_to_db
from lib.models.file import FileRole
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunType
from lib.services.projects import create_project

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/api/start-analysis/_do_not_use_", response_model=StartWorkflowResponse)
async def start_analysis(
    request: AnalysisFormConfig,
    current_user: User = Depends(get_current_user),
):
    # Temporary empty endpoint to force OpenAPI generation for the AnalysisFormConfig object
    return None


@router.post("/api/start-analysis", response_model=StartWorkflowResponse)
async def start_analysis(
    background_tasks: BackgroundTasks,
    main_document: UploadFile = File(...),
    supporting_documents: Optional[list[UploadFile]] = File(default=None),
    config: AnalysisFormConfig = Depends(build_config_from_form),
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
        # Default to document processing if no workflow_types specified
        workflow_types = config.workflow_types or [WorkflowRunType.DOCUMENT_PROCESSING]

        logger.info(
            f"Starting workflows: {[wt.value for wt in workflow_types]} for project {project.id}"
        )

        request = StartMultipleWorkflowsRequest(
            project_id=str(project.id),
            workflow_types=workflow_types,
            openai_api_key=config.openai_api_key,
        )

        await start_multiple_workflow_runs(
            workflow_types=workflow_types,
            request=request,
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


@router.post("/api/preflight", response_model=PreflightResult)
async def check_preflight(
    request: PreflightRequest,
    user: User = Depends(get_current_user),
):
    """Run preflight validation before starting analysis."""
    return await preflight_service.validate(request)
