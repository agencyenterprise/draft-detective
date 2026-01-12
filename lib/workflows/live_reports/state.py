from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.addendum_report_generator import ReportOutput
from lib.agents.evidence_weighter import EvidenceWeighterResponseWithClaimIndex
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class LiveReportsWorkflowConfig(BaseWorkflowConfig):
    """Configuration for the live reports workflow."""

    type: Literal[WorkflowRunType.LIVE_REPORTS] = Field(WorkflowRunType.LIVE_REPORTS)


class LiveReportsState(BaseWorkflowState):
    """State for the live reports workflow."""

    type: Literal[WorkflowRunType.LIVE_REPORTS] = Field(WorkflowRunType.LIVE_REPORTS)
    config: LiveReportsWorkflowConfig
    file_id: str
    live_reports_analysis: List[EvidenceWeighterResponseWithClaimIndex] = Field(
        default_factory=list,
        description="Live reports analysis results aggregated across chunks",
    )
    addendum_report: Optional[ReportOutput] = Field(
        default=None,
        description="Addendum report output for live reports",
    )
