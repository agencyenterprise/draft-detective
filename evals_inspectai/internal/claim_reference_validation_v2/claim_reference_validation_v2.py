"""Internal eval for the CitationValidatorAgent (claim_reference_validation_v2).

Runs the agent directly against a single document section with mocked
file artifacts. Use this layer to grow coverage of citation-validation
behavior cheaply; the e2e flavor (still TODO) covers the full workflow.
"""

from pathlib import Path
from typing import Any, List

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState

from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.internal.claim_reference_validation_v2.solver import (
    citation_validator_solver,
)
from evals_inspectai.internal.common.config import get_model_or_agent_default
from lib.agents.citation_validator import CitationValidatorAgent, SectionValidationResult


@task
def claim_reference_validation_v2():
    dataset = json_dataset(
        str(
            Path(__file__).parent.parent.parent
            / "e2e"
            / "claim_reference_validation_v2"
            / "dataset.json"
        ),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        model=get_model_or_agent_default(CitationValidatorAgent),
        solver=citation_validator_solver(),
        scorer=[
            structured_output_scorer(SectionValidationResult, _grade_alignment),
            issue_count_match(),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


def _record_to_sample(record: dict[str, Any]) -> Sample:
    section = record["section"]
    headings = " > ".join(section.get("headings", [])) or "Document root"
    input_summary = (
        f"Section {headings} (lines {section['start_line']}–{section['end_line']}) "
        f"with {len(record.get('references', []))} references."
    )

    metadata = {
        "main_doc": record["main_doc"],
        "supporting_files": record.get("supporting_files", []),
        "references": record.get("references", []),
        "section": section,
        "domain": record.get("domain"),
        "target_audience": record.get("target_audience"),
        "expected_issues": record.get("expected_issues", []),
        "target_answer": record.get("target_answer", ""),
    }

    return Sample(
        id=record.get("id"),
        input=input_summary,
        target="",  # actual grading uses metadata; target is unused here
        metadata=metadata,
    )


def _grade_alignment(output: SectionValidationResult, state: TaskState) -> Score:
    """Match each expected issue to a produced one and check evidence_alignment.

    Matching is by substring of `quoted_text` (case-insensitive). The score is
    the fraction of expected issues that were both found and tagged with the
    expected alignment level.
    """
    expected: List[dict[str, Any]] = state.metadata.get("expected_issues", []) or []
    if not expected:
        # Nothing to grade against — treat as CORRECT so this scorer doesn't
        # punish samples that only rely on the model-graded rubric.
        return Score(value=CORRECT, explanation="No expected_issues declared")

    matches = 0
    notes: list[str] = []
    for exp in expected:
        needle = exp["quoted_contains"].lower()
        found = next(
            (
                issue
                for issue in output.issues
                if needle in issue.quoted_text.lower()
            ),
            None,
        )
        if not found:
            notes.append(f"missing citation containing '{exp['quoted_contains']}'")
            continue
        if found.evidence_alignment.value != exp["alignment"]:
            notes.append(
                f"'{exp['quoted_contains']}' got {found.evidence_alignment.value}, "
                f"expected {exp['alignment']}"
            )
            continue
        matches += 1

    score_value = matches / len(expected)
    if score_value == 1.0:
        return Score(value=CORRECT, explanation=f"All {matches} expected issues matched")
    return Score(
        value=score_value if score_value > 0 else INCORRECT,
        explanation="; ".join(notes) or "no expected issues matched",
    )


@scorer(metrics=[mean(), stderr()])
def issue_count_match():
    """Score 1.0 if the produced issue count equals the expected count, else 0."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            result = SectionValidationResult.model_validate_json(
                state.output.completion
            )
        except Exception as e:  # noqa: BLE001 — surface parse errors as INCORRECT
            return Score(value=INCORRECT, explanation=f"Parse error: {e}")

        expected = state.metadata.get("expected_issues", []) or []
        actual = len(result.issues)
        if actual == len(expected):
            return Score(value=CORRECT, explanation=f"Issue count matches: {actual}")
        return Score(
            value=INCORRECT,
            explanation=f"Got {actual} issues, expected {len(expected)}",
        )

    return score
