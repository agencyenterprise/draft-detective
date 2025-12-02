"""
Document analysis endpoints
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from api.dependencies import build_config_from_form
from api.models import StartWorkflowResponse
from api.services.workflow_runner import run_workflow_background
from api.upload import convert_uploaded_files_to_file_document
from lib.agents.registry import agent_registry
from lib.models.user import User
from lib.services.projects import create_project
from lib.workflows.claim_substantiation.runner import rerun_analysis
from lib.workflows.claim_substantiation.state import (
    RerunAnalysisRequest,
    SubstantiationWorkflowConfig,
)

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
    Start claim substantiation analysis - returns workflow_run_id immediately.

    This endpoint:
    1. Uploads and converts documents to markdown
    2. Creates a workflow run record in the database
    3. Returns the workflow_run_id immediately
    4. Starts the analysis workflow in the background

    The client can poll /api/workflow-run/{workflow_run_id} to check progress.

    Args:
        background_tasks: FastAPI background tasks
        main_document: The main document to analyze for claims
        supporting_documents: Optional supporting documents for substantiation
        config: Workflow configuration built from form fields

    Returns:
        workflow_run_id and session_id to track the analysis
    """
    try:
        logger.info("Converting uploaded files to markdown...")
        [main_file, *supporting_files] = await convert_uploaded_files_to_file_document(
            [main_document] + (supporting_documents or [])
        )
        logger.info(f"File conversion complete for {main_file.file_name}")

        project = await create_project(title=main_file.file_name, user=current_user)

        logger.info(f"Created project {project.id}")

        background_tasks.add_task(
            run_workflow_background,
            project.id,
            main_file,
            supporting_files,
            config,
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


@router.post("/api/rerun-analysis", response_model=StartWorkflowResponse)
async def rerun_analysis_endpoint(
    request: RerunAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Re-evaluate a specific chunk with selected agents using unified LangGraph workflow.

    Args:
        request: Contains chunk index, agents to run, and original state

    Returns:
        Updated results for the specified chunk
    """
    try:
        if request.config.agents_to_run:
            agent_registry.validate_agents(request.config.agents_to_run)

        background_tasks.add_task(
            rerun_analysis,
            project_id=request.project_id,
            config=request.config,
            current_user=current_user,
        )

        return StartWorkflowResponse(
            project_id=request.project_id,
            message="Analysis re-run started. You can track progress using the workflow_run_id.",
        )

    except ValueError as e:
        logger.error(f"Invalid request for re-running the analysis: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error re-running the analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error re-running the analysis: {str(e)}"
        )
