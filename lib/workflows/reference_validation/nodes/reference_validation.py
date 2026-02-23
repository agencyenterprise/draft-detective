import logging

from langgraph.runtime import Runtime
from langgraph.types import Send

from lib.agents.reference_validator import ReferenceValidatorAgent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_validation.state import (
    ReferenceValidationItem,
    ReferenceValidationState,
    ReferenceValidationStatus,
)

logger = logging.getLogger(__name__)


@register_node(
    "Initialize validations",
    "Initialize all references with pending status",
)
async def initialize_validations(
    state: ReferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Initialize all references with PENDING status immediately.

    This allows the frontend to display all references right away
    before any validation has started.
    """
    file_artifacts_service = runtime.context.file_artifacts_service
    references = await file_artifacts_service.get_extracted_references()

    pending_results = [
        ReferenceValidationItem(
            reference_id=ref.id,
            input_reference=ref.text,
            status=ReferenceValidationStatus.PENDING,
        )
        for ref in references
    ]

    return {"reference_validations": pending_results}


@register_node(
    "Distribute validations",
    "Distribute references to parallel validation operations",
)
async def distribute_validations(
    state: ReferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Fan-out node: creates a Send for each reference.

    This node dispatches parallel validation operations for each reference.
    """
    return [
        Send(
            "validate_single_reference",
            {
                "reference_id": item.reference_id,
                "input_reference": item.input_reference,
            },
        )
        for item in state.reference_validations
    ]


@register_node(
    "Validate reference",
    "Validate a single reference",
)
async def validate_single_reference(state: dict, runtime: Runtime[ContextSchema]):
    """Process a single reference and return status update.

    Each call to this node handles one reference and returns an update
    that the reducer will merge into the state by reference_id.
    """
    reference_id = state["reference_id"]
    input_reference = state["input_reference"]

    agent = ReferenceValidatorAgent(runtime.context)

    validation_result = None
    error = None
    status = ReferenceValidationStatus.COMPLETED

    try:
        validation_result, messages = await agent.ainvoke(
            {"reference": input_reference}
        )
    except Exception as e:
        logger.error(
            f"Error validating reference '{input_reference}': {e}", exc_info=True
        )
        status = ReferenceValidationStatus.ERROR
        error = str(e)

    return {
        "reference_validations": [
            ReferenceValidationItem(
                reference_id=reference_id,
                input_reference=input_reference,
                status=status,
                validation_result=validation_result,
                error=error,
            )
        ]
    }


@register_node(
    "Finalize validations",
    "Finalize validation results",
)
async def finalize_validations(
    state: ReferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Finalize validation results after all parallel validations complete."""
    return {}
