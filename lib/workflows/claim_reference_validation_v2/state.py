"""State, config, and reducer for Claim Reference Validation V2 workflow."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lib.agents.citation_validator import TruthfulnessLabel
from lib.agents.claim_verifier import ClaimEvidenceSource, EvidenceAlignmentLevel
from lib.workflows.agent_messages import AgentMessages
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    ErrorDetails,
    LocatedQuote,
    WorkflowRunType,
)
from lib.workflows.reducers import Reducer, upsert_by


class CitationIssueItem(BaseModel):
    """Persisted workflow-state record for one validated citation.

    Built from the agent's `CitationAssessment` in the validate_section node.
    New runs populate `evidence_alignment` (supported / partially_supported /
    unsupported / unverifiable). The deprecated 6-category `truthfulness_label`
    is retained only so workflow state persisted before the migration back to
    `EvidenceAlignmentLevel` still deserializes; the manifest maps it onto the
    new taxonomy for rendering.
    """

    quoted_text: str
    line_start: int
    line_end: int
    evidence_alignment: EvidenceAlignmentLevel | None = None
    # Deprecated: retained only so pre-migration persisted state still
    # deserializes. New runs never populate it.
    truthfulness_label: TruthfulnessLabel | None = None
    rationale: str = ""
    feedback: str = ""
    evidence_sources: list[ClaimEvidenceSource] = Field(default_factory=list)
    citation_to_file_mapping: str | None = None
    # The cited text, located on one line of the document; None when it could
    # not be (it spans lines, repeats, or is not verbatim), and for states
    # stored before passages existed.
    passage: LocatedQuote | None = None


class ClaimReferenceValidationV2Config(BaseWorkflowConfig):
    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    )


class SectionVerificationStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    # The model's response was cut off mid-output; the assessments it had
    # finished were salvaged, so the section carries both issues and an error.
    PARTIAL = "partial"
    ERROR = "error"
    CANCELLED = "cancelled"


class SectionVerificationItem(BaseModel):
    section_index: int
    start_line: int = 1
    end_line: int = 1
    headings: list[str] = Field(default_factory=list)
    status: SectionVerificationStatus = SectionVerificationStatus.PENDING
    num_citations: int = 0
    issues: list[CitationIssueItem] = Field(default_factory=list)
    error: str | None = None
    error_details: ErrorDetails | None = Field(
        default=None,
        description="Traceback, raw model output, and LLM metadata for a failed section.",
    )
    messages: AgentMessages = Field(
        default_factory=list,
        description="LLM conversation messages from the citation-validator agent invocation.",
    )


# Merges by section_index so each verified section replaces its PENDING row.
merge_section_verifications: Reducer[SectionVerificationItem] = upsert_by(
    lambda s: s.section_index
)


class ClaimReferenceValidationV2State(BaseWorkflowState):
    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    )
    config: ClaimReferenceValidationV2Config

    section_verifications: Annotated[
        list[SectionVerificationItem], merge_section_verifications
    ] = Field(default_factory=list)

    citation_issues: list[CitationIssueItem] = Field(default_factory=list)
