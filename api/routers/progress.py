"""Progress tracking API endpoints."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.models import WorkflowProgressResponse
from lib.models.user import User
from lib.services.authorization import has_access_to_workflow_run
from lib.services.workflow_progress import get_workflow_progress

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get(
    "/workflow/{workflow_run_id}",
    response_model=List[WorkflowProgressResponse],
)
async def get_workflow_progress_endpoint(
    workflow_run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> List[WorkflowProgressResponse]:
    """
    Get all progress entries for a workflow run.

    Returns progress entries ordered by creation time.
    """
    if not has_access_to_workflow_run(current_user, str(workflow_run_id)):
        raise HTTPException(status_code=403, detail="Access denied to this workflow run")

    progress_list = get_workflow_progress(workflow_run_id)
    return [WorkflowProgressResponse.model_validate(p) for p in progress_list]

