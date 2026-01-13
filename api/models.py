from typing import List, Optional
from pydantic import BaseModel

from lib.workflows.models import WorkflowRunType


class StartWorkflowResponse(BaseModel):
    """Response model for starting a workflow"""

    project_id: str | None = None
    workflow_run_id: str | None = None
    type: WorkflowRunType | None = None
    message: str


class StartMultipleWorkflowsRequest(BaseModel):
    """Request model for starting multiple workflows"""

    project_id: str
    workflow_types: List[WorkflowRunType]
    openai_api_key: str | None = None


class AnalysisFormConfig(BaseModel):
    """Form config for starting analysis (project creation + workflow start)"""

    domain: Optional[str] = None
    target_audience: Optional[str] = None
    openai_api_key: Optional[str] = None
    publication_date: Optional[str] = None
    workflow_types: Optional[List[WorkflowRunType]] = None


class StartMultipleWorkflowsResponse(BaseModel):
    """Response model for starting multiple workflows"""

    project_id: str
    types: List[WorkflowRunType]
    workflow_run_ids: List[str]
    message: str
