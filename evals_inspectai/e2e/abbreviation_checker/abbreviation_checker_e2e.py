from pathlib import Path
from typing import Any, List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer


class AbbreviationItem(BaseModel):
    """Local mirror of the API response schema."""

    abbr: str
    inline_definition: str = ""
    occurrence_number: int = 0
    line_start: int = 0
    line_end: int = 0
    abbreviations_section_definition: Optional[str] = None
    ignored: bool = False
    ignored_reason: Optional[str] = None


class AbbreviationCheckOutput(BaseModel):
    """Local mirror of the API response schema."""

    abbreviations: List[AbbreviationItem] = Field(default_factory=list)
    abbreviations_section_found: bool = False
    reasoning: str = ""


@task
def abbreviation_checker_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        FieldSpec(
            target="target_answer",
            metadata=["target_abbreviations_section_found", "target_abbreviations"],
        ),
    )

    return Task(
        # TODO: allow model to be specified dynamically / via api config
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent("abbreviation_scan_v2"),
        scorer=[
            structured_output_scorer(
                AbbreviationCheckOutput, _compare_abbreviation_list
            ),
            structured_output_scorer(
                AbbreviationCheckOutput, _compare_abbreviations_section_found
            ),
            model_graded_check(partial_credit=True),
        ],
    )


def _compare_abbreviations_section_found(
    output: AbbreviationCheckOutput, state: TaskState
) -> bool:
    return (
        str(output.abbreviations_section_found).lower()
        == state.metadata.get("target_abbreviations_section_found", "").lower()
    )


_COMPARE_FIELDS = [
    "inline_definition",
    "line_start",
    "line_end",
    "abbreviations_section_definition",
    "ignored",
]


def _compare_abbreviation_list(
    output: AbbreviationCheckOutput, state: TaskState
) -> Score:
    expected_items: list[dict[str, Any]] = state.metadata.get(
        "target_abbreviations", []
    )
    if not expected_items:
        return Score(value=1.0, explanation="No target abbreviations defined")

    actual_items = [
        item.model_dump(include={"abbr", "occurrence_number", *_COMPARE_FIELDS})
        for item in output.abbreviations
    ]

    return deep_diff_score(expected_items, actual_items)
