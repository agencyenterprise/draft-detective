from enum import Enum
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field

from lib.agents.reference_validator import BibliographyItemValidation
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ReferenceValidationStatus(str, Enum):
    """Status of a reference validation operation"""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"


class ReferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the reference validation workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION] = Field(
        WorkflowRunType.REFERENCE_VALIDATION
    )

    show_invalid_references_as_issues: bool = Field(
        default=True,
        description="When True, invalid references will appear as issues in the Document Explorer. "
        "When False, validation results are only shown in the References tab.",
    )


class ReferenceValidationItem(BaseModel):
    """Item for tracking individual reference validation with status"""

    reference_id: str = Field(description="The ID of the reference to validate.")
    input_reference: str = Field(description="The original reference text.")
    status: ReferenceValidationStatus = Field(
        default=ReferenceValidationStatus.PENDING,
        description="Current status of this reference validation.",
    )
    validation_result: Optional[BibliographyItemValidation] = Field(
        default=None,
        description="The validation result for the reference, present on success.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message, present on failure.",
    )


def merge_validation_results(
    existing: List[ReferenceValidationItem],
    new: List[ReferenceValidationItem],
) -> List[ReferenceValidationItem]:
    """Reducer to merge results by reference_id, preserving order.

    This reducer function is used by LangGraph to handle incremental updates
    from parallel validation operations. Each update overwrites the entry with the
    same reference_id, allowing status transitions from PENDING to COMPLETED/ERROR.
    """
    results_by_id = {r.reference_id: r for r in existing}

    for item in new:
        results_by_id[item.reference_id] = item

    # Return in insertion order (dict preserves order in Python 3.7+)
    return list(results_by_id.values())


class ReferenceValidationState(BaseWorkflowState):
    """State for the reference validation workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION] = Field(
        WorkflowRunType.REFERENCE_VALIDATION
    )
    config: ReferenceValidationWorkflowConfig
    reference_validations: Annotated[
        List[ReferenceValidationItem], merge_validation_results
    ] = Field(default_factory=list)
