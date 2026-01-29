import asyncio
import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.reference_validator import (
    BibliographyItemValidation,
    ReferenceValidatorAgent,
)
from lib.run_utils import run_tasks
from lib.workflows.context import ContextSchema, get_current_workflow_run_id
from lib.services.url_redirect_checker import get_final_url
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError
from lib.workflows.reference_extraction.state import ExtractedReference
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

    # Fetch extracted references (no file matching needed for validation)
    references = await file_artifacts_service.get_extracted_references()

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
    workflow_run_id = get_current_workflow_run_id()
    for index, exception in enumerate(exceptions):
        if exception is not None:
            errors.append(
                WorkflowError(
                    task_name="validate_references",
                    error=str(exception),
                    workflow_run_id=workflow_run_id,
                )
            )

    return {"reference_validations": validation_responses, "errors": errors}


async def _validate_reference(
    reference: ExtractedReference,
    reference_validator_agent: ReferenceValidatorAgent,
) -> BibliographyItemValidation:
    llm_task = reference_validator_agent.ainvoke({"reference": reference.text})
    url_task = get_final_url(reference.text)

    llm_result, url_result = await asyncio.gather(
        llm_task, url_task, return_exceptions=True
    )

    if isinstance(llm_result, Exception):
        raise llm_result

    if not isinstance(url_result, Exception):
        cited_url, final_url = url_result
        if cited_url:
            llm_result.cited_url = cited_url
            if final_url and final_url != cited_url:
                llm_result.url = final_url

    return llm_result
