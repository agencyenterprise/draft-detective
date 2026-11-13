"""Review Assistant requests: the outputs an author wants from their documents."""

from fastapi import APIRouter, Depends

from lib.api.auth import get_current_user
from lib.api.models import StartWorkflowResponse
from lib.api.services.workflow_runner import start_workflow_run
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.projects.service import get_project_access
from lib.services.review_assistant_requests import (
    ReviewAssistantRequestSummary,
    StartReviewAssistantRequest,
    assert_project_files,
    list_review_assistant_requests,
    record_request,
    request_config,
)

router = APIRouter(tags=["review-assistant"])


@router.post(
    "/api/project/{project_id}/review-assistant/requests",
    response_model=StartWorkflowResponse,
)
async def start_review_assistant_request_endpoint(
    project_id: str,
    request: StartReviewAssistantRequest,
    user: User = Depends(get_current_user),
):
    """Start a request: produce these outputs from these documents."""
    await get_project_access(project_id, user=user, required_level=AccessLevel.WRITE)
    config = request_config(project_id, request)
    await assert_project_files(project_id, config.input_file_ids)

    # Recorded before the run can be queued: the runner's state writes come after.
    workflow_run_id = await start_workflow_run(
        config=config,
        user=user,
        on_created=lambda run_id: record_request(run_id, config),
    )
    return StartWorkflowResponse(
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        type=config.type,
        message="Review Assistant request started.",
    )


@router.get(
    "/api/project/{project_id}/review-assistant/requests",
    response_model=list[ReviewAssistantRequestSummary],
)
async def list_review_assistant_requests_endpoint(
    project_id: str,
    user: User = Depends(get_current_user),
):
    """The project's requests across every revision, newest first."""
    await get_project_access(project_id, user=user)
    return await list_review_assistant_requests(project_id)
