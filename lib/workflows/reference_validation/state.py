from typing import List, Literal

from pydantic import Field

from lib.agents.models import BibliographyItem
from lib.agents.reference_validator import BibliographyItemValidation
from lib.workflows.base import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ReferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the reference validation workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION] = Field(
        WorkflowRunType.REFERENCE_VALIDATION
    )


class ReferenceValidationState(BaseWorkflowState):
    """State for the reference validation workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION] = Field(
        WorkflowRunType.REFERENCE_VALIDATION
    )
    config: ReferenceValidationWorkflowConfig
    references: List[BibliographyItem] = Field(default_factory=list)
    reference_validations: List[BibliographyItemValidation] = Field(
        default_factory=list
    )
