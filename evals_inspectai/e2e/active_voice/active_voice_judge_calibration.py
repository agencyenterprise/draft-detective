"""Calibrate the Active Voice edit judge against human-labelled pairs, as an Inspect task.

Each sample is one proposed edit with a reviewer's verdict for
``meaning_preserved`` and ``reads_well`` (``calibration/edit_pairs.yaml``).
There is nothing to generate: the solver hands the replacement through as the
output, and the scorer grades it with the same criteria and prompts the eval
uses, then compares the grade with the label. Metrics report agreement, and
the true-positive and true-negative rates separately, because raw agreement
hides a judge that always passes. Run this before trusting a criterion change,
and read the disagreements in ``inspect view``.

Usage::

    uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_judge_calibration.py --model-role grader=openai/gpt-5.4
    uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_judge_calibration.py -T calls=3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import get_model
from inspect_ai.scorer import Metric, SampleScore, Score, Scorer, Target, accuracy, metric, scorer
from inspect_ai.solver import Generate, Solver, TaskState, solver

from evals_inspectai.common.loaders import yaml_dataset
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL
from evals_inspectai.common.issue_judge import edit_prompt, grade
from evals_inspectai.e2e.active_voice.criteria import MEANING_CRITERION, READS_CRITERION

PAIRS = Path(__file__).parent / "calibration" / "edit_pairs.yaml"
CRITERIA = {"meaning_preserved": MEANING_CRITERION, "reads_well": READS_CRITERION}


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        id=record["id"],
        input=record["original"],
        target=[record["meaning_preserved"], record["reads_well"]],
        metadata={
            "paragraph": record.get("paragraph", record["original"]),
            "replacement": record["replacement"],
            "labels": {name: record[name] for name in CRITERIA},
            "note": record.get("note", ""),
        },
    )


@solver
def replacement_as_output() -> Solver:
    """The edit under test is already written; make it the sample's output."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.output.completion = state.metadata["replacement"]
        return state

    return solve


@metric
def true_positive_rate() -> Metric:
    """Of the pairs the reviewer passed, the share the judge also passed."""

    def compute(scores: list[SampleScore]) -> float:
        positives = [s for s in scores if (s.score.metadata or {}).get("label") == "pass"]
        return sum(s.score.as_float() for s in positives) / len(positives) if positives else float("nan")

    return compute


@metric
def true_negative_rate() -> Metric:
    """Of the pairs the reviewer failed, the share the judge also failed."""

    def compute(scores: list[SampleScore]) -> float:
        negatives = [s for s in scores if (s.score.metadata or {}).get("label") == "fail"]
        return sum(s.score.as_float() for s in negatives) / len(negatives) if negatives else float("nan")

    return compute


def _judge_agreement(name: str, criterion: str, calls: int) -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        value, why = await grade(
            grader,
            edit_prompt(criterion, state.metadata["paragraph"], state.input_text, state.output.completion),
            calls,
        )
        label = state.metadata["labels"][name]
        judged = "pass" if value >= 0.75 else "fail"
        return Score(
            value=float(judged == label),
            answer=judged,
            explanation=f"labelled {label}, judged {judged} ({value}); {state.metadata['note']}\n\n{why}",
            metadata={"label": label, "grade": value},
        )

    return score


@scorer(metrics=[accuracy(), true_positive_rate(), true_negative_rate()])
def meaning_agreement(calls: int = 1) -> Scorer:
    return _judge_agreement("meaning_preserved", MEANING_CRITERION, calls)


@scorer(metrics=[accuracy(), true_positive_rate(), true_negative_rate()])
def reads_agreement(calls: int = 1) -> Scorer:
    return _judge_agreement("reads_well", READS_CRITERION, calls)


@task
def active_voice_judge_calibration(calls: int = 1) -> Task:
    return Task(
        dataset=yaml_dataset(PAIRS, _record_to_sample),
        solver=replacement_as_output(),
        scorer=[meaning_agreement(calls), reads_agreement(calls)],
    )
