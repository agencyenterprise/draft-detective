import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from starlette.responses import FileResponse

from api.auth import get_current_user, get_current_user_optional
from api.models import (
    ApproveCheckpointRequest,
    ApproveCheckpointResponse,
    StartMultipleWorkflowsRequest,
    StartMultipleWorkflowsResponse,
    StartWorkflowResponse,
)
from api.services.workflow_runner import (
    start_multiple_workflow_runs,
    start_workflow_run,
)
from lib.config.database import get_db
from lib.config.env import config
from lib.models.share_link import ShareLink
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.authorization import has_access_to_workflow_run
from lib.services.projects import create_project, get_user_project
from lib.services.workflow_runs import (
    WorkflowRunDetail,
    get_project_workflow_run_by_type,
    get_thread_id_for_workflow_run,
    get_workflow_run,
    get_workflow_run_state,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.human_approval.state import HumanApprovalConfig
from lib.workflows.models import WorkflowRunType
from lib.workflows.runner import run_workflow_with_dependency_check
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
    "/api/project/{project_id}/approve",
    response_model=ApproveCheckpointResponse,
)
async def approve_checkpoint(
    project_id: str,
    request: ApproveCheckpointRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Approve a human checkpoint and trigger workflow completion.

    This marks the HUMAN_APPROVAL workflow as ready to complete,
    which unblocks any dependent workflows (e.g., CLAIM_REFERENCE_VALIDATION).
    """
    await get_user_project(project_id, user=current_user)

    workflow_run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.HUMAN_APPROVAL
    )

    if workflow_run is None:
        raise HTTPException(
            status_code=404,
            detail="Human approval workflow not found for this project",
        )

    if workflow_run.status == WorkflowRunStatus.COMPLETED:
        return ApproveCheckpointResponse(
            message="Already approved",
            checkpoint=request.checkpoint,
            workflow_run_id=str(workflow_run.id),
        )

    config = HumanApprovalConfig(
        project_id=project_id,
        checkpoint=request.checkpoint,
    )
    thread_id = get_thread_id_for_workflow_run(workflow_run)

    background_tasks.add_task(
        run_workflow_with_dependency_check,
        config=config,
        thread_id=thread_id,
        workflow_run_id=str(workflow_run.id),
        user=current_user,
    )

    return ApproveCheckpointResponse(
        message=f"Checkpoint '{request.checkpoint}' approved",
        checkpoint=request.checkpoint,
        workflow_run_id=str(workflow_run.id),
    )
