from enum import Enum
from typing import Annotated, List, Literal, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_serializer

from lib.agents.reference_validator_v2 import BibliographyItemValidationV2
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ReferenceValidationV2Status(str, Enum):
    """Status of a reference validation operation"""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class ReferenceValidationV2WorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the reference validation v2 workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.REFERENCE_VALIDATION_V2
    )


class ReferenceValidationV2Item(BaseModel):
    """Item for tracking individual reference validation with status"""

    reference_id: str = Field(description="The ID of the reference to validate.")
    input_reference: str = Field(description="The original reference text.")
    status: ReferenceValidationV2Status = Field(
        default=ReferenceValidationV2Status.PENDING,
        description="Current status of this reference validation.",
    )
    validation_result: Optional[BibliographyItemValidationV2] = Field(
        default=None,
        description="The validation result for the reference, present on success.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message, present on failure.",
    )
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="LLM conversation messages from the agent invocation.",
    )

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        return [m.model_dump() for m in messages]


def merge_validation_results(
    existing: List[ReferenceValidationV2Item],
    new: List[ReferenceValidationV2Item],
) -> List[ReferenceValidationV2Item]:
    """Reducer to merge results by reference_id, preserving order."""
    results_by_id = {r.reference_id: r for r in existing}

    for item in new:
        results_by_id[item.reference_id] = item

    return list(results_by_id.values())


class ReferenceValidationV2State(BaseWorkflowState):
    """State for the reference validation v2 workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.REFERENCE_VALIDATION_V2
    )
    config: ReferenceValidationV2WorkflowConfig
    reference_validations: Annotated[
        List[ReferenceValidationV2Item], merge_validation_results
    ] = Field(default_factory=list)
