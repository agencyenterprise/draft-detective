from typing import Optional

from fastapi import APIRouter, Depends

from lib.api.auth import get_current_user_optional
from lib.models.user import User
from lib.services.workflow_types import (
    WorkflowTypesResponse,
    get_workflow_types_for_user,
)

router = APIRouter(tags=["workflow-types"])


@router.get("/api/workflow-types", response_model=WorkflowTypesResponse)
async def get_workflow_types(user: Optional[User] = Depends(get_current_user_optional)):
    """
    List available workflow types and ordered category display config based on user permissions.

    QA Screener workflows are only visible to RAND and ADMIN roles.
    """
    return get_workflow_types_for_user(user)
