from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import _workflow_manifest_registry

router = APIRouter(tags=["workflow-types"])


class WorkflowTypeDescription(BaseModel):
    type: WorkflowRunType = Field(description="The type of the workflow")
    name: str = Field(description="The name of the workflow")
    description: str = Field(description="The description of the workflow")
    needs_web_search: bool = Field(description="Whether the workflow needs web search")
    is_experimental: bool = Field(description="Whether the workflow is experimental")
    is_internal: bool = Field(
        description="Whether the workflow is internal (runs as a dependency, not shown in UI)"
    )
    can_be_triggered_by_user: bool = Field(
        description="Whether the workflow can be manually triggered by a user"
    )
    order: int = Field(
        description="Display order in the UI (lower numbers appear first)"
    )


@router.get("/api/workflow-types", response_model=List[WorkflowTypeDescription])
async def get_workflow_types():
    """
    List all available workflow types including internal ones.
    """
    workflow_types = []

    for workflow_type, manifest in _workflow_manifest_registry.items():
        workflow_types.append(
            WorkflowTypeDescription(
                type=manifest.type,
                name=manifest.name,
                description=manifest.description,
                needs_web_search=manifest.needs_web_search,
                is_experimental=manifest.is_experimental,
                is_internal=manifest.is_internal,
                can_be_triggered_by_user=manifest.can_be_triggered_by_user,
                order=manifest.order,
            )
        )

    # Sort by order for consistent ordering
    workflow_types.sort(key=lambda x: x.order)

    return workflow_types
