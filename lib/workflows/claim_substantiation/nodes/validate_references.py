import logging

from langgraph.runtime import Runtime

from lib.agents.reference_validator import ReferenceValidatorAgent
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Validate references",
    "Validate the references for the document",
)
async def validate_references(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    reference_validator_agent = ReferenceValidatorAgent(runtime.context)
    validate_references_response = await reference_validator_agent.ainvoke(
        {
            "references": state.references,
        }
    )

    return {"references_validated": validate_references_response.reference_validations}
