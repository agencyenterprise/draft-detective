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
from lib.workflows.error_details import capture_error_details
from lib.workflows.models import (
    ErrorDetails,
    ProposedEdit,
    WorkflowError,
    WorkflowErrorSeverity,
)
from lib.workflows.reference_validation_v2.edits import build_reference_edits
from lib.workflows.reference_validation_v2.state import (
    ReferenceValidationV2Item,
    ReferenceValidationV2State,
    ReferenceValidationV2Status,
)
from lib.workflows.simple_deep_agent.edit_anchoring import document_lines

logger = logging.getLogger(__name__)

# How much of a reference's text names it in a user-facing error.
MAX_REFERENCE_LABEL_CHARS = 120


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
    error_details: ErrorDetails | None = None
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
        error_details = capture_error_details(e)

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
                error_details=error_details,
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


def _reference_error_message(item: ReferenceValidationV2Item) -> str:
    """State what the reader lost; the exception itself stays on `details`."""
    reference = item.input_reference
    if len(reference) > MAX_REFERENCE_LABEL_CHARS:
        reference = reference[:MAX_REFERENCE_LABEL_CHARS] + "..."
    return (
        f'Reference "{reference}" could not be validated. It is missing from '
        f"these results. {item.error or 'Unknown error'}"
    )


@register_node("Finalize validations")
async def finalize_validations(
    state: ReferenceValidationV2State, runtime: Runtime[ContextSchema]
):
    """Report every reference that failed as a run-level error.

    A failed reference costs one entry, not the run, so it is a warning while
    other references were validated. When none were, an empty result would
    read as an all-clear, so the failures escalate to errors.
    """
    produced_results = any(
        item.status == ReferenceValidationV2Status.COMPLETED
        for item in state.reference_validations
    )
    severity = (
        WorkflowErrorSeverity.WARNING
        if produced_results
        else WorkflowErrorSeverity.ERROR
    )
    errors = [
        WorkflowError(
            task_name="validate_single_reference",
            error=_reference_error_message(item),
            workflow_run_id=runtime.context.workflow_run_id,
            severity=severity,
            details=item.error_details,
        )
        for item in state.reference_validations
        if item.status == ReferenceValidationV2Status.ERROR
    ]
    return {"errors": errors}
