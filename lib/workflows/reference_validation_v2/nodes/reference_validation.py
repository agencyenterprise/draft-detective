import logging

from langchain_core.messages import BaseMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite, Send

from lib.agents.reference_validator_v2 import (
    BibliographyItemValidationV2,
    ReferenceValidatorV2Agent,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import ProposedEdit
from lib.workflows.reference_validation_v2.edits import build_reference_edits
from lib.workflows.reference_validation_v2.state import (
    ReferenceValidationV2Item,
    ReferenceValidationV2State,
    ReferenceValidationV2Status,
)
from lib.workflows.simple_deep_agent.edit_anchoring import document_lines

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
    """Fan-out router: creates a Send for each reference."""
    references = await runtime.context.file_artifacts_service.get_extracted_references()
    # Each reference's place in the document, to anchor its edits on.
    lines_by_id = {
        ref.id: {"start_line": ref.start_line, "end_line": ref.end_line}
        for ref in references
    }
    return [
        Send(
            "validate_single_reference",
            {
                "reference_id": item.reference_id,
                "input_reference": item.input_reference,
                **lines_by_id.get(item.reference_id, {}),
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
    agent_messages: list[BaseMessage] = []

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

    edits: list[ProposedEdit] = []
    if validation_result is not None:
        # An edit is extra: failing to place one must not lose the validation.
        try:
            edits = await _reference_edits(validation_result, state, runtime.context)
        except Exception:
            logger.warning(
                f"Could not build edits for reference '{input_reference}'",
                exc_info=True,
            )

    return {
        "reference_validations": [
            ReferenceValidationV2Item(
                reference_id=reference_id,
                input_reference=input_reference,
                status=status,
                validation_result=validation_result,
                error=error,
                edits=edits,
                messages=agent_messages,
            )
        ]
    }


async def _reference_edits(
    result: BibliographyItemValidationV2, state: dict, context: ContextSchema
) -> list[ProposedEdit]:
    """Edits that apply a confident correction on the reference's own lines."""
    start_line, end_line = state.get("start_line"), state.get("end_line")
    if start_line is None or end_line is None:
        return []
    document = await context.file_artifacts_service.get_main_file()
    return build_reference_edits(
        result,
        state["input_reference"],
        document_lines(document.markdown),
        start_line,
        end_line,
    )


@register_node("Finalize validations")
async def finalize_validations(
    state: ReferenceValidationV2State, runtime: Runtime[ContextSchema]
):
    """Finalize validation results after all parallel validations complete."""
    return {}
