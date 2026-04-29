from pathlib import Path
from typing import List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import CORRECT, INCORRECT, Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer


class BibliographyFieldValidation(BaseModel):
    """Local mirror of the API response schema."""

    category: str = ""
    problem_type: str = ""
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None


class BibliographyItemValidationOutput(BaseModel):
    """Local mirror of BibliographyItemValidation API response schema."""

    final_result: str = ""
    original_reference: str = ""
    suggested_action: str = ""
    updated_reference: Optional[str] = None
    bibliography_field_validations: List[BibliographyFieldValidation] = Field(
        default_factory=list
    )
    reasoning: str = ""


class ReferenceValidationItem(BaseModel):
    """Local mirror of ReferenceValidationItem API response schema."""

    reference_id: str = ""
    input_reference: str = ""
    status: str = ""
    validation_result: Optional[BibliographyItemValidationOutput] = None
    error: Optional[str] = None


class ReferenceValidationOutput(BaseModel):
    """Local mirror of the reference_validation workflow state."""

    reference_validations: List[ReferenceValidationItem] = Field(default_factory=list)


def _record_to_sample(record: dict) -> Sample:
    reference = record["input"]
    document_content = f"## References\n\n{reference}\n"
    return Sample(
        input=document_content,
        target=record.get("target_final_result", ""),
        metadata={"target_answer": record.get("target_answer", "")},
    )


@task
def reference_validation_e2e():
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent(
            "reference_validation_v2",
        ),
        scorer=[
            structured_output_scorer(ReferenceValidationOutput, _compare_final_result),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


def _compare_final_result(output: ReferenceValidationOutput, state: TaskState) -> Score:
    if not output.reference_validations:
        return Score(value=INCORRECT, explanation="No reference validations found")

    first = output.reference_validations[0]
    if first.error:
        raise WorkflowCompletionError(
            f"Reference '{first.input_reference}' failed: {first.error}"
        )
    if first.validation_result is None:
        return Score(value=INCORRECT, explanation="No validation result found")

    actual = first.validation_result.final_result
    expected = state.target.text
    if actual == expected:
        return Score(value=CORRECT, explanation=f"final_result matches: {actual}")
    return Score(
        value=INCORRECT,
        explanation=f"Expected '{expected}', got '{actual}'",
    )
