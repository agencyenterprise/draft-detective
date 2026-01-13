import logging
from typing import List

from langgraph.runtime import Runtime

from lib.models.bibliography_item import BibliographyItem
from lib.agents.reference_validator import (
    BibliographyItemValidation,
    ReferenceValidatorAgent,
)
from lib.run_utils import run_tasks
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError
from lib.workflows.reference_validation.state import ReferenceValidationState

logger = logging.getLogger(__name__)


@register_node(
    "Validate references",
    "Validate the references for the document",
)
async def reference_validation(
    state: ReferenceValidationState, runtime: Runtime[ContextSchema]
):
    reference_validator_agent = ReferenceValidatorAgent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch references from file artifacts service
    references = await file_artifacts_service.get_references()

    tasks = [
        _validate_reference(reference, reference_validator_agent)
        for reference in references
    ]

    results: tuple[list[BibliographyItemValidation | None], list[Exception | None]] = (
        await run_tasks(tasks, desc="Validating references")
    )
    validation_responses_raw, exceptions = results

    validation_responses: List[BibliographyItemValidation] = []
    for validation_response in validation_responses_raw:
        if validation_response is not None:
            validation_responses.append(validation_response)

    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            errors.append(
                WorkflowError(
                    task_name="validate_references",
                    error=str(exception),
                )
            )

    return {"reference_validations": validation_responses, "errors": errors}


async def _validate_reference(
    reference: BibliographyItem,
    reference_validator_agent: ReferenceValidatorAgent,
) -> BibliographyItemValidation:
    return await reference_validator_agent.ainvoke(
        {
            "reference": reference.text,
        }
    )
