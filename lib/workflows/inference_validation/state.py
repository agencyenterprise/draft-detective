from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.inference_validator import InferenceValidationResponseWithClaimIndex
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class InferenceValidationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the inference validation workflow."""

    type: Literal[WorkflowRunType.INFERENCE_VALIDATION] = Field(
        WorkflowRunType.INFERENCE_VALIDATION
    )
    domain: Optional[str] = Field(
        default=None, description="Domain context for more accurate analysis"
    )
    target_audience: Optional[str] = Field(
        default=None, description="Target audience context for analysis"
    )


class InferenceValidationState(BaseWorkflowState):
    """State for the inference validation workflow."""

    type: Literal[WorkflowRunType.INFERENCE_VALIDATION] = Field(
        WorkflowRunType.INFERENCE_VALIDATION
    )
    config: InferenceValidationWorkflowConfig
    file_id: str
    inference_validations: List[InferenceValidationResponseWithClaimIndex] = Field(
        default_factory=list
    )
