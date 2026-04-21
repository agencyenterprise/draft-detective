"""State, config, and reducer for Claim Reference Validation V2 workflow."""

from enum import Enum
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field

from lib.agents.citation_validator import CitationIssueItem
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ClaimReferenceValidationV2Config(BaseWorkflowConfig):
    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    )


class SectionVerificationStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class SectionVerificationItem(BaseModel):
    section_index: int
    start_line: int = 1
    end_line: int = 1
    headings: List[str] = Field(default_factory=list)
    status: SectionVerificationStatus = SectionVerificationStatus.PENDING
    num_citations: int = 0
    issues: List[CitationIssueItem] = Field(default_factory=list)
    error: Optional[str] = None


def merge_section_verifications(
    existing: List[SectionVerificationItem],
    new: List[SectionVerificationItem],
) -> List[SectionVerificationItem]:
    """Reducer: merge by section_index, allowing PENDING → COMPLETED/ERROR transitions."""
    by_index = {item.section_index: item for item in existing}
    for item in new:
        by_index[item.section_index] = item
    return list(by_index.values())


class ClaimReferenceValidationV2State(BaseWorkflowState):
    type: Literal[WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    )
    config: ClaimReferenceValidationV2Config

    section_verifications: Annotated[
        List[SectionVerificationItem], merge_section_verifications
    ] = Field(default_factory=list)

    citation_issues: List[CitationIssueItem] = Field(default_factory=list)
