from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lib.workflows.models import WorkflowRunType, is_user_visible_workflow
from lib.workflows.registry import _workflow_manifest_registry

router = APIRouter(tags=["workflow-types"])


class WorkflowTypeDescription(BaseModel):
    type: WorkflowRunType = Field(description="The type of the workflow")
    name: str = Field(description="The name of the workflow")
    description: str = Field(description="The description of the workflow")
    needs_web_search: bool = Field(description="Whether the workflow needs web search")
    is_internal: bool = Field(description="Whether the workflow is internal")
    is_experimental: bool = Field(description="Whether the workflow is experimental")
    can_be_triggered_by_user: bool = Field(
        description="Whether the workflow can be triggered by the user"
    )


@router.get("/api/workflow-types", response_model=List[WorkflowTypeDescription])
async def get_workflow_types():
    """
    List all available workflow types.
    """
    workflow_types: List[WorkflowTypeDescription] = []

    for workflow_type, manifest in _workflow_manifest_registry.items():
        if (
            is_user_visible_workflow(workflow_type)
            and manifest.can_be_triggered_by_user
        ):
            workflow_types.append(
                WorkflowTypeDescription(
                    type=manifest.type,
                    name=manifest.name,
                    description=manifest.description,
                    needs_web_search=manifest.needs_web_search,
                    is_internal=manifest.is_internal,
                    is_experimental=manifest.is_experimental,
                    can_be_triggered_by_user=manifest.can_be_triggered_by_user,
                )
            )

    # Sort by name for consistent ordering
    workflow_types.sort(key=lambda x: x.name)

    return workflow_types
