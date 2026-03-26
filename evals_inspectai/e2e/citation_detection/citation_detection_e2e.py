from pathlib import Path
from typing import Any, List

from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.scorers import structured_output_scorer

_COMPARE_FIELDS = [
    "text",
    "type",
    "needs_bibliography",
    "associated_bibliography",
    "index_of_associated_bibliography",
]


class Citation(BaseModel):
    """Local mirror of the Citation API response schema."""

    text: str = ""
    type: str = ""
    format: str = ""
    needs_bibliography: bool = False
    associated_bibliography: str = ""
    index_of_associated_bibliography: int = -1
    rationale: str = ""


class CitationResponse(BaseModel):
    """Local mirror of the CitationResponse API response schema."""

    citations: List[Citation] = Field(default_factory=list)
    rationale: str = ""
    chunk_index: int = 0


class CitationDetectionOutput(BaseModel):
    """Local mirror of the citation_detection workflow state."""

    citations: List[CitationResponse] = Field(default_factory=list)


@task
def citation_detection_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        FieldSpec(
            input="input",
            metadata=["target_citations"],
        ),
    )

    return Task(
        dataset=dataset,
        solver=api_workflow_agent("citation_detection"),
        scorer=structured_output_scorer(CitationDetectionOutput, _compare_citations),
    )


def _compare_citations(output: CitationDetectionOutput, state: TaskState) -> Score:
    expected: list[dict[str, Any]] = state.metadata.get("target_citations", [])

    actual = [
        citation.model_dump(include=set(_COMPARE_FIELDS))
        for chunk_result in output.citations
        for citation in chunk_result.citations
    ]

    return deep_diff_score(expected, actual)
