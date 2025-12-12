import logging

from langgraph.runtime import Runtime

from lib.agents.reference_validator import ReferenceValidatorAgent
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
    references = "\n\n".join([reference.text for reference in state.references])

    validate_references_response = await reference_validator_agent.ainvoke(
        {
            "references": references,
        }
    )

    return {"reference_validations": validate_references_response.reference_validations}
