import json
import logging

from langgraph.runtime import Runtime

from lib.agents.inference_synthesizer import InferenceSynthesizerAgent
from lib.agents.inference_validator_v2 import InferenceResultResponse
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.inference_validation_v2.nodes.validate_inferences_v2 import (
    NUM_VALIDATOR_RUNS,
)
from lib.workflows.inference_validation_v2.state import InferenceValidationV2State

logger = logging.getLogger(__name__)


@register_node(
    "Synthesize inferences",
    "Consolidate validator runs: merge, disambiguate, and rank by severity.",
)
async def synthesize_inferences(
    state: InferenceValidationV2State, runtime: Runtime[ContextSchema]
):
    """Collect validator results, run synthesizer agent, write consolidated result."""
    validator_results = state.validator_results or {}
    ordered = [
        validator_results.get(i) or InferenceResultResponse(results=[])
        for i in range(1, NUM_VALIDATOR_RUNS + 1)
    ]

    file_artifacts_service = runtime.context.file_artifacts_service
    file_document = await file_artifacts_service.get_file_document(state.file_id)
    markdown = file_document.markdown

    logger.info(
        "synthesize_inferences: Running synthesizer agent on %s runs",
        NUM_VALIDATOR_RUNS,
    )
    agent = InferenceSynthesizerAgent(runtime.context)

    # gather input
    consolidated_input = {"full_document": markdown}
    for i in range(NUM_VALIDATOR_RUNS):
        consolidated_input[f"run{i+1}_json"] = json.dumps(
            [x.model_dump() for x in ordered[i].results], indent=2
        )

    consolidated = await agent.ainvoke(consolidated_input)
    return {"inference_results": consolidated}
