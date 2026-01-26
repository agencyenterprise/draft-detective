import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from starlette.responses import FileResponse

from api.auth import get_current_user, get_current_user_optional
from api.models import (
    ApproveWorkflowResponse,
    StartMultipleWorkflowsRequest,
    StartMultipleWorkflowsResponse,
    StartWorkflowResponse,
)
from api.services.workflow_runner import (
    resume_workflow_run,
    start_multiple_workflow_runs,
    start_workflow_run,
)
from lib.config.env import config
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.authorization import has_access_to_workflow_run
from lib.services.projects import create_project
from lib.services.workflow_runs import (
    WorkflowRunDetail,
    get_workflow_run,
    get_workflow_run_state,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.human_approval.state import HumanApprovalConfig
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.types import WorkflowConfig

router = APIRouter(tags=["workflows"])


@router.post("/api/workflows/start", response_model=StartWorkflowResponse)
async def start_workflow(
    request: WorkflowConfig,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Start a workflow"""

    # TODO: Remove this once we have a proper project creation flow and/or move the
    # reference downloader to tool inside a project
    if (
        request.project_id is None
        and request.type == WorkflowRunType.REFERENCE_DOWNLOADER
    ):
        project = await create_project(
            title=f"Reference Downloader {datetime.utcnow():%Y-%m-%d %H:%M UTC}",
            user=user,
        )
        request.project_id = str(project.id)

    workflow_run_id = await start_workflow_run(
        config=request, user=user, background_tasks=background_tasks
    )

    return StartWorkflowResponse(
        project_id=request.project_id,
        workflow_run_id=workflow_run_id,
        type=request.type,
        message=f"Workflow started. Track progress by polling the workflow result endpoint `/api/workflows/{workflow_run_id}`.",
    )


@router.post("/api/workflows/start-multiple", response_model=StartWorkflowResponse)
async def start_multiple_workflows(
    request: StartMultipleWorkflowsRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Start multiple workflow analyses for a project."""

    workflow_run_ids = await start_multiple_workflow_runs(
        workflow_types=request.workflow_types,
        request=request,
        user=user,
        background_tasks=background_tasks,
    )

    return StartMultipleWorkflowsResponse(
        project_id=request.project_id,
        types=request.workflow_types,
        workflow_run_ids=workflow_run_ids,
        message="Workflows started. Track progress by polling the project endpoint `/api/project/{project_id}`.",
    )


@router.get("/api/workflows/{workflow_run_id}", response_model=WorkflowRunDetail)
async def get_workflow_state(
    workflow_run_id: str, user: User = Depends(get_current_user)
):
    """Get the state of a workflow"""

    run = await get_workflow_run(workflow_run_id, user=user)
    state = await get_workflow_run_state_by_thread_id(run.langgraph_thread_id, run.type)
    return WorkflowRunDetail(run=run, state=state)


@router.get("/api/workflow-runs/{workflow_run_id}/pages/{page_num}")
async def get_page_image(
    workflow_run_id: str,
    page_num: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Serve Docling page images for a workflow run.

    Allows access if user is authenticated OR if the project has sharing enabled.

    Args:
        workflow_run_id: The workflow run ID
        page_num: The page number (e.g., 0, 1, 2, etc.)

    Returns:
        The image file for the specified page (PNG, JPEG, WEBP, etc.)
    """
    if page_num < 0:
        raise HTTPException(status_code=400, detail="Invalid page number")

    if not has_access_to_workflow_run(current_user, workflow_run_id):
        raise HTTPException(status_code=403, detail="Access denied")

    state = await get_workflow_run_state(workflow_run_id, user=None)

    if not hasattr(state, "file"):
        raise HTTPException(status_code=404, detail="Workflow state not found")

    file_path = state.file.file_path
    filename = os.path.basename(file_path)
    file_id, _ = os.path.splitext(filename)

    images_dir = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, "docling_images", file_id)
    image_file_path = os.path.join(images_dir, f"page_{page_num}.png")

    if os.path.exists(image_file_path):
        return FileResponse(
            path=image_file_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    raise HTTPException(status_code=404, detail=f"Page {page_num} not found")


@router.post(
    "/api/workflow-runs/{workflow_run_id}/approve",
    response_model=ApproveWorkflowResponse,
)
async def approve_workflow_run(
    workflow_run_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Approve a workflow run that requires human approval.

    The workflow must:
    1. Exist and belong to a project owned by the current user
    2. Be a workflow type that supports human approval (requires_human_trigger=True)

    This unblocks any dependent workflows (e.g., CLAIM_REFERENCE_VALIDATION).
    """
    workflow_run = await get_workflow_run(workflow_run_id, user=current_user)

    # Validate this workflow type supports human approval
    manifest = get_workflow_manifest(workflow_run.type)
    if not manifest.requires_human_trigger:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow type '{workflow_run.type.value}' does not require human approval",
        )

    if workflow_run.status == WorkflowRunStatus.COMPLETED:
        return ApproveWorkflowResponse(
            message="Already approved",
            workflow_run_id=workflow_run_id,
        )

    approval_config = HumanApprovalConfig(
        project_id=str(workflow_run.project_id),
    )

    await resume_workflow_run(workflow_run, approval_config, current_user, background_tasks)

    return ApproveWorkflowResponse(
        message="Workflow approved",
        workflow_run_id=workflow_run_id,
    )
