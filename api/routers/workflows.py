from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.auth import get_current_user
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
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.workflow_runs import (
    WorkflowRunDetail,
    get_workflow_run,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.human_approval.state import HumanApprovalConfig
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

    await resume_workflow_run(
        workflow_run, approval_config, current_user, background_tasks
    )

    return ApproveWorkflowResponse(
        message="Workflow approved",
        workflow_run_id=workflow_run_id,
    )
