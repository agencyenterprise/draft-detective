import logging

from langgraph.runtime import Runtime

from lib.agents.reference_validator import ReferenceValidatorAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


@handle_workflow_node_errors()
async def validate_references(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"validate_references ({state.config.session_id}): starting")

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "validate_references" not in agents_to_run:
        logger.info(
            f"validate_references ({state.config.session_id}): Skipping validate references (not in agents_to_run)"
        )
        return {}

    reference_validator_agent = ReferenceValidatorAgent(runtime.context)
    validate_references_response = await reference_validator_agent.ainvoke(
        {
            "references": state.references,
        }
    )

    logger.info(f"validate_references ({state.config.session_id}): done")

    return {"references_validated": validate_references_response.reference_validations}
