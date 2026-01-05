from datetime import date
from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.addendum_report_generator import ReportOutput
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.evidence_weighter import EvidenceWeighterResponseWithClaimIndex
from lib.agents.reference_extractor import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class LiveReportsWorkflowConfig(BaseWorkflowConfig):
    """Configuration for the live reports workflow."""

    type: Literal[WorkflowRunType.LIVE_REPORTS] = Field(WorkflowRunType.LIVE_REPORTS)


class LiveReportsState(BaseWorkflowState):
    """State for the live reports workflow."""

    type: Literal[WorkflowRunType.LIVE_REPORTS] = Field(WorkflowRunType.LIVE_REPORTS)
    config: LiveReportsWorkflowConfig
    file: FileDocument
    references: List[BibliographyItem] = Field(default_factory=list)
    chunks: List[AnalyzedChunk] = Field(default_factory=list)
    main_document_summary: DocumentSummary = Field(
        description="Summary of the main document"
    )
    live_reports_analysis: List[EvidenceWeighterResponseWithClaimIndex] = Field(
        default_factory=list,
        description="Live reports analysis results aggregated across chunks",
    )
    addendum_report: Optional[ReportOutput] = Field(
        default=None,
        description="Addendum report output for live reports",
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[AnalyzedChunk]:
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])
