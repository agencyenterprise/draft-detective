# lib/workflows/results_extraction/state.py
from lib.workflows.results_extraction.agents.results_extractor import (
    ResultsListResponse,
)
from lib.models.workflow_run import WorkflowRunType
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState
from typing import Literal, Optional
from pydantic import Field


class ResultsExtractionState(BaseWorkflowState):
    type: Literal[WorkflowRunType.RESULTS_EXTRACTION] = Field(
        WorkflowRunType.RESULTS_EXTRACTION
    )
    file_id: str = Field(description="The ID of the file to extract results from")
    results: Optional[ResultsListResponse] = Field(
        default=None, description="Extracted results with reproducibility assessments"
    )


class ResultsExtractionWorkflowConfig(BaseWorkflowConfig):
    type: Literal[WorkflowRunType.RESULTS_EXTRACTION] = Field(
        WorkflowRunType.RESULTS_EXTRACTION
    )
