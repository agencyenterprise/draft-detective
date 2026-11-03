from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lib.agents.reference_validator_v2 import BibliographyItemValidationV2
from lib.workflows.agent_messages import AgentMessages
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    ErrorDetails,
    ProposedEdit,
    WorkflowRunType,
)
from lib.workflows.reducers import Reducer, upsert_by


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
    validation_result: BibliographyItemValidationV2 | None = Field(
        default=None,
        description="The validation result for the reference, present on success.",
    )
    error: str | None = Field(
        default=None,
        description="Error message, present on failure.",
    )
    error_details: ErrorDetails | None = Field(
        default=None,
        description="Traceback and raw model output behind `error`, for debugging.",
    )
    edits: list[ProposedEdit] = Field(
        default_factory=list,
        description=(
            "Tracked-change edits that apply the validator's correction, located "
            "on the reference's line. Empty unless the fix is not in doubt."
        ),
    )
    messages: AgentMessages = Field(
        default_factory=list,
        description="LLM conversation messages from the agent invocation.",
    )


# Merges by reference_id so each validation result replaces its PENDING row.
merge_validation_results: Reducer[ReferenceValidationV2Item] = upsert_by(
    lambda r: r.reference_id
)


class ReferenceValidationV2State(BaseWorkflowState):
    """State for the reference validation v2 workflow."""

    type: Literal[WorkflowRunType.REFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.REFERENCE_VALIDATION_V2
    )
    config: ReferenceValidationV2WorkflowConfig
    reference_validations: Annotated[
        list[ReferenceValidationV2Item], merge_validation_results
    ] = Field(default_factory=list)
