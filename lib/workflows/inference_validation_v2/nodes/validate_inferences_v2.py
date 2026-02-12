import logging

from langgraph.runtime import Runtime

from lib.agents.inference_validator_v2 import (
    InferenceResultResponse,
    InferenceValidatorV2Agent,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.inference_validation_v2.state import InferenceValidationV2State

logger = logging.getLogger(__name__)

NUM_VALIDATOR_RUNS = 3


@register_node(
    "Prepare inference runs",
    "No-op entry node; fans out to parallel validator runs.",
)
async def prepare_inference_runs(
    state: InferenceValidationV2State, runtime: Runtime[ContextSchema]
) -> dict:
    """No-op: allows graph to fan out to validator nodes from a single entry."""
    return {}


async def _run_single_validator(
    state: InferenceValidationV2State,
    runtime: Runtime[ContextSchema],
    run_index: int,
) -> dict:
    """Load document, run InferenceValidatorV2Agent once, return state update."""
    file_artifacts_service = runtime.context.file_artifacts_service
    file_document = await file_artifacts_service.get_file_document(state.file_id)
    markdown = file_document.markdown

    agent = InferenceValidatorV2Agent(runtime.context)
    try:
        response = await agent.ainvoke(
            {"text": markdown}, config={"run_index": run_index}
        )
        return {"validator_results": {run_index: response}}
    except Exception as e:
        logger.error(
            "validate_inference_%s: Inference validator failed: %s",
            run_index,
            e,
            exc_info=True,
        )
        return {"validator_results": {run_index: InferenceResultResponse(results=[])}}


def _make_validator_node(run_index: int):
    """Factory: returns a registered validator node for the given run index."""

    async def node(
        state: InferenceValidationV2State, runtime: Runtime[ContextSchema]
    ) -> dict:
        return await _run_single_validator(state, runtime, run_index)

    # Set __name__ before the decorator runs so agents_to_run
    # sees "validate_inference_1" etc., not "node".
    node.__name__ = f"validate_inference_{run_index}"

    decorator = register_node(
        f"Validate inferences run {run_index}",
        f"Run {run_index} of {NUM_VALIDATOR_RUNS} parallel inference validator runs.",
    )

    return decorator(node)


VALIDATOR_NODES = {
    f"validate_inference_{i}": _make_validator_node(i)
    for i in range(1, NUM_VALIDATOR_RUNS + 1)
}
