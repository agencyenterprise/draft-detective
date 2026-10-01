"""Output-first review assistant: start a run on picked inputs, list its runs."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from lib.api.auth import get_current_user
from lib.api.models import StartMultipleWorkflowsRequest, StartWorkflowResponse
from lib.api.services.workflow_runner import start_multiple_workflow_runs
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.projects import get_project_access
from lib.services.review_assistant_runs import (
    ReviewAssistantInputs,
    ReviewAssistantRun,
    ReviewInputsError,
    list_review_assistant_runs,
    resolve_input_files,
    seed_run_inputs,
)
from lib.workflows.models import WorkflowRunType

router = APIRouter(tags=["review-assistant"])


class StartReviewAssistantRunRequest(BaseModel):
    """One review-assistant output, run on the files picked for its inputs."""

    project_id: str
    output: WorkflowRunType = Field(
        description=(
            "revision_planning_summary, reviewer_response_memos or "
            "reviewer_coverage_report"
        )
    )
    inputs: ReviewAssistantInputs
    model: Optional[str] = None


@router.post("/api/review-assistant/runs", response_model=StartWorkflowResponse)
async def start_review_assistant_run(
    request: StartReviewAssistantRunRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Start a review-assistant output on explicitly picked inputs."""
    await get_project_access(
        request.project_id, user=user, required_level=AccessLevel.WRITE
    )
    try:
        input_files = await resolve_input_files(
            request.project_id, request.output, request.inputs
        )
    except ReviewInputsError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run_ids = await start_multiple_workflow_runs(
        workflow_types=[request.output],
        request=StartMultipleWorkflowsRequest(
            project_id=request.project_id,
            workflow_types=[request.output],
            model=request.model,
        ),
        user=user,
        background_tasks=background_tasks,
        config_updates={request.output: {"input_files": input_files}},
    )
    run_id = await seed_run_inputs(
        run_ids, request.project_id, request.output, input_files, request.model
    )
    return StartWorkflowResponse(
        project_id=request.project_id,
        workflow_run_id=run_id,
        type=request.output,
        message="Started. Track it with the review-assistant runs endpoint.",
    )


@router.get(
    "/api/review-assistant/projects/{project_id}/runs",
    response_model=List[ReviewAssistantRun],
)
async def list_review_assistant_runs_endpoint(
    project_id: str,
    output: WorkflowRunType = Query(description="The review-assistant output"),
    user: User = Depends(get_current_user),
):
    """Runs of an output that were started on picked inputs, newest first."""
    await get_project_access(project_id, user=user)
    return await list_review_assistant_runs(project_id, output)
