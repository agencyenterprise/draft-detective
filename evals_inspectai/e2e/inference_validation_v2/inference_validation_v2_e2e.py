from pathlib import Path
from typing import List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer


class InferenceResult(BaseModel):
    """Local mirror of ExtractedInferenceResult."""

    key_sentence: str = ""
    severity: str = ""
    inference_validity: bool = True
    short_form_argument_analysis: str = ""
    long_form_argument_analysis: str = ""
    suggested_action: str = ""
    chunk_indices: List[int] = Field(default_factory=list)


class InferenceResultsResponse(BaseModel):
    results: List[InferenceResult] = Field(default_factory=list)


class InferenceValidationOutput(BaseModel):
    """Local mirror of InferenceValidationV2State.inference_results."""

    inference_results: Optional[InferenceResultsResponse] = None


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=record["input"],
        target=record.get("target_answer", ""),
        metadata={
            "expected_invalid_count": record["expected_invalid_count"],
        },
    )


@task
def inference_validation_v2_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent("inference_validation_v2", timeout_s=600),
        scorer=[
            structured_output_scorer(
                InferenceValidationOutput, _compare_invalid_count
            ),
            model_graded_check(partial_credit=True),
        ],
    )


def _invalid_count(output: InferenceValidationOutput) -> int:
    if output.inference_results is None:
        return 0
    return sum(1 for r in output.inference_results.results if not r.inference_validity)


def _compare_invalid_count(
    output: InferenceValidationOutput, state: TaskState
) -> Score:
    expected: int = state.metadata["expected_invalid_count"]
    actual = _invalid_count(output)

    if actual == expected:
        return Score(
            value=1.0,
            explanation=f"Invalid-inference count matches expected ({expected})",
        )
    return Score(
        value=0.0,
        explanation=f"Expected {expected} invalid inferences, got {actual}",
    )
