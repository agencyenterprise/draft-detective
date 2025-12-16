import logging

from langgraph.runtime import Runtime

from lib.agents.reference_extractor import BibliographyItem
from lib.agents.reference_validator import (
    BibliographyItemValidation,
    ReferenceValidatorAgent,
)
from lib.run_utils import run_tasks
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_validation.state import ReferenceValidationState

logger = logging.getLogger(__name__)


@register_node(
    "Validate references",
    "Validate the references for the document",
)
async def reference_validation(
    state: ReferenceValidationState, runtime: Runtime[ContextSchema]
) -> ReferenceValidationState:
    reference_validator_agent = ReferenceValidatorAgent(runtime.context)

    tasks = [
        _validate_reference(reference, reference_validator_agent)
        for reference in state.references
    ]

    results: tuple[list[BibliographyItemValidation], list[Exception]] = await run_tasks(
        tasks, desc="Validating references"
    )
    validation_responses, exceptions = results

    return {"reference_validations": validation_responses}


async def _validate_reference(
    reference: BibliographyItem,
    reference_validator_agent: ReferenceValidatorAgent,
) -> BibliographyItemValidation:
    return await reference_validator_agent.ainvoke(
        {
            "reference": reference.text,
        }
    )
