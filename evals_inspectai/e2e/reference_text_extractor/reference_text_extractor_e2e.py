from pathlib import Path
from typing import List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.common.scorers import structured_output_scorer


class ExtractedReference(BaseModel):
    """Local mirror of the API response schema."""

    id: str = ""
    text: str = ""
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class ReferenceExtractionOutput(BaseModel):
    """Local mirror of the API response schema."""

    extracted_references: List[ExtractedReference] = Field(default_factory=list)
    reasoning: str = ""


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=resolve_input(record["input"]),
        metadata={"target_references": record.get("target_references", [])},
    )


@task
def reference_text_extractor_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        solver=api_workflow_agent("reference_extraction"),
        scorer=[
            structured_output_scorer(ReferenceExtractionOutput, _compare_references),
        ],
    )


def _compare_references(output: ReferenceExtractionOutput, state: TaskState) -> Score:
    expected_refs: list[str] = state.metadata.get("target_references", [])
    actual_refs = [ref.text for ref in output.extracted_references]
    return deep_diff_score(expected_refs, actual_refs)
