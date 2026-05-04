import logging
from typing import List

from langchain_core.messages import BaseMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite, Send

from lib.agents.reference_validator_v2 import ReferenceValidatorV2Agent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_validation_v2.state import (
    ReferenceValidationV2Item,
    ReferenceValidationV2State,
    ReferenceValidationV2Status,
)

logger = logging.getLogger(__name__)


@register_node("Initialize validations")
async def initialize_validations(
    state: ReferenceValidationV2State, runtime: Runtime[ContextSchema]
):
    """Initialize all references with PENDING status immediately."""
    file_artifacts_service = runtime.context.file_artifacts_service
    references = await file_artifacts_service.get_extracted_references()

    pending_results = [
        ReferenceValidationV2Item(
            reference_id=ref.id,
            input_reference=ref.text,
            status=ReferenceValidationV2Status.PENDING,
        )
        for ref in references
    ]

    return {"reference_validations": Overwrite(pending_results)}


@register_node("Distribute validations")
async def distribute_validations(
    state: ReferenceValidationV2State, runtime: Runtime[ContextSchema]
):
    """Fan-out node: creates a Send for each reference."""
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


@register_node("Validate reference")
async def validate_single_reference(state: dict, runtime: Runtime[ContextSchema]):
    """Process a single reference and return status update."""
    reference_id = state["reference_id"]
    input_reference = state["input_reference"]

    agent = ReferenceValidatorV2Agent(runtime.context)

    validation_result = None
    error = None
    status = ReferenceValidationV2Status.COMPLETED
    agent_messages: List[BaseMessage] = []

    try:
        validation_result, agent_messages = await agent.ainvoke(
            {"reference": input_reference}
        )
    except Exception as e:
        logger.error(
            f"Error validating reference '{input_reference}': {e}", exc_info=True
        )
        status = ReferenceValidationV2Status.ERROR
        error = str(e)

    return {
        "reference_validations": [
            ReferenceValidationV2Item(
                reference_id=reference_id,
                input_reference=input_reference,
                status=status,
                validation_result=validation_result,
                error=error,
                messages=agent_messages,
            )
        ]
    }


@register_node("Finalize validations")
async def finalize_validations(
    state: ReferenceValidationV2State, runtime: Runtime[ContextSchema]
):
    """Finalize validation results after all parallel validations complete."""
    return {}
