from typing import Annotated, Dict, Literal, Optional, List

from pydantic import Field

from lib.agents.inference_synthesizer import (
    ConsolidatedInferenceAnalysis,
    ConsolidatedInferenceResultResponse,
)
from lib.agents.inference_validator_v2 import InferenceResultResponse
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class ExtractedInferenceResult(ConsolidatedInferenceAnalysis):
    """An inference result with document-derived chunk indices."""

    chunk_indices: List[int] = Field(
        default_factory=list,
        description="Chunk indices that overlap with the inference (by line range).",
    )


class ExtractedInferenceResultResponse(ConsolidatedInferenceResultResponse):
    """Response containing extracted inference results with chunk indices."""

    results: List[ExtractedInferenceResult] = Field(
        description="Consolidated inference results with line and chunk info.",
    )


def merge_validator_results(
    existing: Dict[int, InferenceResultResponse],
    new: Dict[int, InferenceResultResponse],
) -> Dict[int, InferenceResultResponse]:
    """Reducer to merge parallel validator run results by run index (1, 2, 3, ...)."""
    out = dict(existing)
    out.update(new)
    return out


class InferenceValidationV2State(BaseWorkflowState):
    """State for the inference validation v2 workflow."""

    type: Literal[WorkflowRunType.INFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.INFERENCE_VALIDATION_V2
    )
    file_id: str = Field(
        description="The ID of the main source document",
    )

    validator_results: Annotated[
        Dict[int, InferenceResultResponse], merge_validator_results
    ] = Field(
        default_factory=dict,
        description="Results from parallel inference validator runs keyed by run index (1, 2, 3, ...)",
    )

    inference_results: Optional[ExtractedInferenceResultResponse] = Field(
        default=None,
        description="Consolidated inference analysis result with severity",
    )


class InferenceValidationV2WorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the inference validation v2 workflow."""

    type: Literal[WorkflowRunType.INFERENCE_VALIDATION_V2] = Field(
        WorkflowRunType.INFERENCE_VALIDATION_V2
    )
