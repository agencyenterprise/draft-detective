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
from typing import List

from pydantic import BaseModel, Field
from lib.workflows.inference_validation_v2.state import (
    InferenceValidationV2State,
    ExtractedInferenceResultResponse,
    ExtractedInferenceResult,
)
from lib.services.chunk_line_matcher import find_chunks_by_line_range

logger = logging.getLogger(__name__)


@register_node(
    "Synthesize inferences",
    "Consolidate validator runs: merge, disambiguate, and rank by severity.",
)
async def synthesize_inferences(
    state: InferenceValidationV2State, runtime: Runtime[ContextSchema]
) -> dict[str, ExtractedInferenceResultResponse]:
    """Collect validator results, run synthesizer agent, write consolidated result."""
    validator_results = state.validator_results or {}
    ordered = [
        validator_results.get(i) or InferenceResultResponse(results=[])
        for i in range(1, NUM_VALIDATOR_RUNS + 1)
    ]

    file_artifacts_service = runtime.context.file_artifacts_service
    file_document = await file_artifacts_service.get_file_document(state.file_id)
    markdown = file_document.markdown

    # add line numbers to markdown for downstream processing
    lines = markdown.split("\n")
    numbered_markdown_lines = [f"{i+1}| {line}" for i, line in enumerate(lines)]
    numbered_markdown = "\n".join(numbered_markdown_lines)

    logger.info(
        "synthesize_inferences: Running synthesizer agent on %s runs",
        NUM_VALIDATOR_RUNS,
    )
    agent = InferenceSynthesizerAgent(runtime.context)

    # gather input
    consolidated_input = {"full_document": numbered_markdown}
    for i in range(NUM_VALIDATOR_RUNS):
        consolidated_input[f"run{i+1}_json"] = json.dumps(
            [x.model_dump() for x in ordered[i].results], indent=2
        )

    consolidated = await agent.ainvoke(consolidated_input)

    # add chunk indices to consolidated inference results
    chunks = await runtime.context.file_artifacts_service.get_chunks()
    extracted_inference_results: List[ExtractedInferenceResult] = []
    for result in consolidated.results:
        chunk_indices: List[int] = []
        if chunks:
            chunk_indices = find_chunks_by_line_range(
                chunks, result.start_line, result.end_line
            )
        extracted_inference_results.append(
            ExtractedInferenceResult(
                key_sentence=result.key_sentence,
                severity=result.severity,
                inference_validity=result.inference_validity,
                short_form_argument_analysis=result.short_form_argument_analysis,
                long_form_argument_analysis=result.long_form_argument_analysis,
                suggested_action=result.suggested_action,
                start_line=result.start_line,
                end_line=result.end_line,
                chunk_indices=chunk_indices,
            )
        )

    return {
        "inference_results": ExtractedInferenceResultResponse(
            results=extracted_inference_results
        )
    }
