# lib/workflows/results_extraction/state.py
from lib.workflows.results_extraction.agents.results_extractor import (
    ResultsListResponse,
)
from lib.models.workflow_run import WorkflowRunType
from lib.services.file import FileDocument
from lib.workflows.base import BaseWorkflowConfig, BaseWorkflowState
from typing import Literal, Optional
from pydantic import Field


class ResultsExtractionState(BaseWorkflowState):
    type: Literal[WorkflowRunType.RESULTS_EXTRACTION] = Field(
        WorkflowRunType.RESULTS_EXTRACTION
    )
    file: FileDocument = Field(description="The main source document")
    results: Optional[ResultsListResponse] = Field(
        default=None, description="Extracted results with reproducibility assessments"
    )


class ResultsExtractionWorkflowConfig(BaseWorkflowConfig):
    type: Literal[WorkflowRunType.RESULTS_EXTRACTION] = Field(
        WorkflowRunType.RESULTS_EXTRACTION
    )
