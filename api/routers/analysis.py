"""
Document analysis endpoints
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.auth import get_current_user
from api.dependencies import build_config_from_form
from api.services.workflow_runner import run_workflow_background
from api.upload import convert_uploaded_files_to_file_document
from lib.agents.registry import agent_registry
from lib.config.database import get_db
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.workflows.claim_substantiation.runner import reevaluate_single_chunk
from lib.workflows.claim_substantiation.state import (
    ChunkReevaluationRequest,
    ChunkReevaluationResponse,
    SubstantiationWorkflowConfig,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


class StartAnalysisResponse(BaseModel):
    """Response model for starting an async analysis workflow"""

    workflow_run_id: str
    session_id: str
    message: str


@router.post("/api/start-analysis", response_model=StartAnalysisResponse)
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

        if not config.session_id:
            config.session_id = str(uuid.uuid4())

        with get_db() as db:
            workflow_run = WorkflowRun(
                langgraph_thread_id=config.session_id,
                title=main_file.file_name,
                status=WorkflowRunStatus.PENDING,
                user_id=current_user.id,
            )
            db.add(workflow_run)
            db.commit()
            db.refresh(workflow_run)
            workflow_run_id = str(workflow_run.id)

        logger.info(
            f"Created workflow run {workflow_run_id} for session {config.session_id}"
        )

        background_tasks.add_task(
            run_workflow_background,
            main_file,
            supporting_files,
            config,
        )

        return StartAnalysisResponse(
            workflow_run_id=workflow_run_id,
            session_id=config.session_id,
            message="Analysis started. You can track progress using the workflow_run_id.",
        )

    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error starting analysis: {str(e)}"
        )


@router.post("/api/reevaluate-chunk", response_model=ChunkReevaluationResponse)
async def reevaluate_chunk(
    request: ChunkReevaluationRequest, current_user: User = Depends(get_current_user)
):
    """
    Re-evaluate a specific chunk with selected agents using unified LangGraph workflow.

    Args:
        request: Contains chunk index, agents to run, and original state

    Returns:
        Updated results for the specified chunk
    """
    try:
        agent_registry.validate_agents(request.agents_to_run)

        import time

        start_time = time.time()

        config_overrides = (
            SubstantiationWorkflowConfig(
                session_id=request.session_id or str(uuid.uuid4())
            )
            if request.session_id
            else None
        )

        updated_state = await reevaluate_single_chunk(
            original_result=request.original_state,
            chunk_index=request.chunk_index,
            agents_to_run=request.agents_to_run,
            config_overrides=config_overrides,
        )

        processing_time_ms = (time.time() - start_time) * 1000

        return ChunkReevaluationResponse(
            state=updated_state,
            agents_run=request.agents_to_run,
            processing_time_ms=processing_time_ms,
        )

    except ValueError as e:
        logger.error(f"Invalid request for chunk re-evaluation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error re-evaluating chunk: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error re-evaluating chunk: {str(e)}"
        )
