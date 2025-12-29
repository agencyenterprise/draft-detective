from pydantic import BaseModel

from lib.workflows.base import WorkflowRunType


class StartWorkflowResponse(BaseModel):
    """Response model for starting a workflow"""

    project_id: str | None = None
    workflow_run_id: str | None = None
    type: WorkflowRunType | None = None
    message: str
