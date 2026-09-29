"""E2E eval for the Reviewer 2 workflow.

Declared by ``skills/reviewer-2/SKILL.md``; runs through the API like every
other e2e eval. The workflow writes a four-section peer review and a
devil's-advocate rebuttal, both prose, so ground truth is not an issue
inventory: ``dataset.yaml`` names, per document, the substantive weaknesses a
rigorous review raises and the genuine strengths it credits. The documents
span the disciplines the persona is asked to channel (an incentive design, a
historical case study, a claim about AI and security, qualitative interviews,
a volunteer-panel survey, a theoretical argument undermined by its own
example), internal inconsistencies between an abstract and its table,
alternative explanations the document itself reports, a chart whose truncated
axis exaggerates a sub-point effect, and a strong pre-registered trial whose
bounded conclusions a contrarian review would wrongly attack.

Scorers: ``review_structure``, deterministic (both documents produced, the
four sections, five to seven next steps, the header blocks), and
``review_judged``, one grader call per planted point plus three per sample
(see ``criteria.py``). No ``tool_called("view_image")``: the state carries the
two documents and no transcript, so the figure sample's weaknesses, which exist
only in the chart, are the proof instead.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/reviewer_2/reviewer_2_e2e.py --epochs 3
"""

import asyncio
import json
import math
from pathlib import Path
from typing import Optional

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState
from inspect_ai.viewer import (
    ScoreColorScale,
    TaskSamplesColumn,
    TaskSamplesSort,
    TaskSamplesView,
    ViewerConfig,
)
from pydantic import ValidationError

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import PER_KEY_METRICS
from evals_inspectai.common.issue_judge import grade
from evals_inspectai.common.loaders import resolve_input, yaml_dataset
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL
from evals_inspectai.e2e.reviewer_2.criteria import (
    CLAIMS_ACCURATE,
    JUDGE_DESCRIPTIONS,
    JUDGED_KEYS,
    NEXT_STEPS_CONCRETE,
    REBUTTAL_CONCEDES,
    SCORE_LABELS,
    STRENGTH_CREDITED,
    STRENGTH_NOT_ATTACKED,
    STRUCTURE_DESCRIPTIONS,
    WEAKNESS_RAISED,
    Reviewer2Output,
    Reviewer2Record,
    review_prompt,
    structure_scores,
)

WORKFLOW_TYPE = "reviewer_2"
DATASET = Path(__file__).parent / "dataset.yaml"


def _record_to_sample(raw: dict) -> Sample:
    record = Reviewer2Record.model_validate(raw)
    return Sample(input=resolve_input(record.input), metadata={"record": record.model_dump()})


def _output(state: TaskState) -> tuple[Optional[Reviewer2Output], Optional[str]]:
    try:
        return Reviewer2Output.model_validate(json.loads(state.output.completion)), None
    except (ValueError, ValidationError) as e:
        return None, f"could not parse the workflow state: {e}"


@scorer(metrics=PER_KEY_METRICS)
def review_structure() -> Scorer:
    """Deterministic checks of the two documents' shape against the skill."""

    async def score(state: TaskState, target: Target) -> Score:
        output, error = _output(state)
        if output is None:
            return Score(value={key: 0.0 for key in STRUCTURE_DESCRIPTIONS}, explanation=error)
        record = Reviewer2Record.model_validate(state.metadata["record"])
        values, explanation = structure_scores(output, state.input_text, record.authors)
        return Score(value=values, explanation=explanation)

    return score


async def _mean_grade(grader: Model, prompts: list[tuple[str, str]], calls: int) -> tuple[float, list[str]]:
    """The mean grade over the labelled prompts (NaN for none), with the label and grade of
    each one below full marks."""
    if not prompts:
        return math.nan, []
    graded = await asyncio.gather(*(grade(grader, prompt, calls) for _, prompt in prompts))
    below = [f"{label} {value}" for (label, _), (value, _) in zip(prompts, graded) if value < 1.0]
    return sum(v for v, _ in graded) / len(graded), below


async def judge_review(grader: Model, document: str, output: Reviewer2Output, record: Reviewer2Record, calls: int) -> tuple[dict[str, float], str]:
    review, rebuttal = output.peer_review_markdown or "", output.rebuttal_markdown or ""

    def on_review(criterion: str, point: Optional[str] = None) -> str:
        return review_prompt(criterion, document, "Peer review", review, point)

    per_point = {
        "weaknesses_raised": [(w.id, on_review(WEAKNESS_RAISED, w.point)) for w in record.weaknesses],
        "strengths_credited": [(s.id, on_review(STRENGTH_CREDITED, s.point)) for s in record.strengths],
        "strengths_not_attacked": [(s.id, on_review(STRENGTH_NOT_ATTACKED, s.point)) for s in record.strengths],
        "claims_accurate": [("review", on_review(CLAIMS_ACCURATE))],
        "next_steps_concrete": [("review", on_review(NEXT_STEPS_CONCRETE))],
        "rebuttal_concedes": [("rebuttal", review_prompt(REBUTTAL_CONCEDES, document, "Rebuttal", rebuttal))] if rebuttal.strip() else [],
    }
    results = await asyncio.gather(*(_mean_grade(grader, per_point[key], calls) for key in JUDGED_KEYS))
    values = {key: value for key, (value, _) in zip(JUDGED_KEYS, results)}
    notes = [f"{key}: {', '.join(below)}" for key, (_, below) in zip(JUDGED_KEYS, results) if below]
    if not rebuttal.strip():
        values["rebuttal_concedes"] = 0.0
        notes.append("rebuttal_concedes: no rebuttal produced")
    return values, " | ".join(notes) if notes else "all judged criteria passed"


@scorer(metrics=PER_KEY_METRICS)
def review_judged(calls: int = 1) -> Scorer:
    """The graded criteria: per planted weakness and strength, and once per sample."""

    async def score(state: TaskState, target: Target) -> Score:
        output, error = _output(state)
        if output is None or not (output.peer_review_markdown or "").strip():
            return Score(value={key: 0.0 for key in JUDGED_KEYS}, explanation=error or "no peer review produced")
        record = Reviewer2Record.model_validate(state.metadata["record"])
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        values, explanation = await judge_review(grader, state.input_text, output, record, calls)
        return Score(value=values, explanation=explanation)

    return score


def _viewer() -> ViewerConfig:
    scored = [*(("review_structure", k) for k in STRUCTURE_DESCRIPTIONS), *(("review_judged", k) for k in JUDGED_KEYS)]
    return ViewerConfig(
        task_samples_view=TaskSamplesView(
            name="Checks by sample and epoch",
            columns=[
                TaskSamplesColumn(id="sampleStatus"),
                TaskSamplesColumn(id="sampleId"),
                TaskSamplesColumn(id="epoch"),
                TaskSamplesColumn(id="input"),
                *(TaskSamplesColumn.score(s, k) for s, k in scored),
                TaskSamplesColumn(id="error"),
                TaskSamplesColumn(id="duration"),
                TaskSamplesColumn(id="target", visible=False),
                TaskSamplesColumn(id="answer", visible=False),
            ],
            sort=[TaskSamplesSort(column="sampleId", dir="asc"), TaskSamplesSort(column="epoch", dir="asc")],
            compact_scores=True,
            multiline=False,
            score_labels=SCORE_LABELS,
            score_color_scales={k: ScoreColorScale(palette="good-high", min=0.0, max=1.0) for _, k in scored},
            color_scales_enabled=True,
        )
    )


@task
def reviewer_2_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Reviewer 2 on every sample and score the review and rebuttal.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded point; the median grade is kept.
    """
    return Task(
        dataset=yaml_dataset(DATASET, _record_to_sample),
        metadata={
            "ground_truth": (
                "Per document, the substantive weaknesses a rigorous review raises and the genuine strengths it "
                "credits, each graded on its own, plus the skill's required structure. A NaN metric value means the "
                "sample gave that check nothing to judge."
            ),
            "metrics": {"review_structure": STRUCTURE_DESCRIPTIONS, "review_judged": JUDGE_DESCRIPTIONS},
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[review_structure(), review_judged(calls=judge_calls)],
        fail_on_error=0.2,
        viewer=_viewer(),
    )
