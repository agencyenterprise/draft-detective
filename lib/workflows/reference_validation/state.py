from typing import List, Literal

from openai import BaseModel
from pydantic import Field

from lib.agents.reference_validator import BibliographyItemValidation
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ReferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the reference validation workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION] = Field(
        WorkflowRunType.REFERENCE_VALIDATION
    )

    show_invalid_references_as_issues: bool = Field(
        default=False,
        description="When True, invalid references will appear as issues in the Document Explorer. "
        "When False (default), validation results are only shown in the References tab.",
    )


class ReferenceValidationItem(BaseModel):
    reference_id: str = Field(description="The ID of the reference to validate.")
    validation_result: BibliographyItemValidation = Field(
        description="The validation result for the reference."
    )


class ReferenceValidationState(BaseWorkflowState):
    """State for the reference validation workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION] = Field(
        WorkflowRunType.REFERENCE_VALIDATION
    )
    config: ReferenceValidationWorkflowConfig
    reference_validations: List[ReferenceValidationItem] = Field(default_factory=list)
