"""E2E eval for the Methodological Alignment workflow, on the issue-inventory structure.

The workflow is a simple deep agent running the ``methodology-comparison``
skill: it extracts the paper's methodology, characterises the field baseline
through web search, reports each missing standard component or methodological
risk as a line-anchored issue, and writes the full comparison to
``report_markdown``.

Ground truth is ``dataset.yaml``: the methods of ten short papers across
fields (a field study, NLP, a clinical trial, a survey, econometrics, medical
imaging, qualitative interviews, field ecology, an online experiment, a
laboratory experiment), each with two to four planted risks and one to three
sound choices. The field baseline comes from live web search, so no wording
or source is asserted.

Scorers: ``report_checks`` (the skill's five sections, web links, no
informational issue); ``plant_checks`` (some issue on each planted risk's line,
at a fitting severity); and ``methodology_judged``, which grades whether an
issue on the line names the planted risk, whether its action repairs it, and
whether the run left each sound choice alone (see ``criteria``). The skill
reports every gap it finds, not only the planted ones, so there is no
precision against the plants; the sound choices are the false-positive check.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/methodological_alignment/methodological_alignment_e2e.py --epochs 3
"""

import asyncio
import math
from pathlib import Path
from typing import Sequence

from inspect_ai import Task, task
from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    PER_KEY_METRICS,
    deterministic_scorer,
    fraction,
    inventory_from_state,
    issues_from_state,
    ranked_hits,
)
from evals_inspectai.common.issue_inventory import ResolvedInventory, inventory_dataset, load_inventory_records
from evals_inspectai.common.issue_judge import gist, grade
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL
from evals_inspectai.common.simple_deep_agent_types import IssueItem, SimpleDeepAgentOutput
from evals_inspectai.e2e.methodological_alignment.criteria import (
    GAP_CRITERION,
    JUDGE_DESCRIPTIONS,
    JUDGED_KEYS,
    OWN_DESCRIPTIONS,
    PLANT_DESCRIPTIONS,
    REPAIR_CRITERION,
    SCORE_LABELS,
    decoy_prompt,
    gap_prompt,
    report_scores,
    severity_fits,
)

WORKFLOW_TYPE = "methodological_alignment"
DATASET = Path(__file__).parent / "dataset.yaml"


def plant_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``recall``, ``anchor_in_range`` and ``severity_fits`` over the planted risks (see ``PLANT_DESCRIPTIONS``)."""
    plants = [e for e in inventory.expected_issues if e.required]
    on_line = {e.id: [issues[i] for i in ranked_hits(e, issues)] for e in plants}
    covered = [e for e in plants if on_line[e.id]]
    high = [e for e in covered if e.severity]
    values = {
        "recall": len(covered) / len(plants) if plants else math.nan,
        "anchor_in_range": fraction([float(any(i.start_line <= (e.line or 0) <= i.end_line for i in on_line[e.id])) for e in covered]),
        "severity_fits": fraction([float(severity_fits(e, on_line[e.id])) for e in high]),
    }
    missing = [e.id for e in plants if not on_line[e.id]]
    misjudged = [e.id for e in high if not severity_fits(e, on_line[e.id])]
    notes = [f"recall {len(covered)}/{len(plants)}" + (f" (nothing on the line of {', '.join(missing)})" if missing else "")]
    notes += [f"high-severity plants reported low: {misjudged}"] if misjudged else []
    return values, " | ".join(notes)


async def judge_methodology(
    grader: Model, issues: Sequence[IssueItem], inventory: ResolvedInventory, calls: int = 1
) -> tuple[dict[str, float], str]:
    """``gap_identified``, ``action_repairs`` and ``sound_choices_respected`` (see ``criteria``)."""
    document = inventory.document
    gaps: list[float] = []
    actions: list[float] = []
    notes: list[str] = []
    for plant in (e for e in inventory.expected_issues if e.required):
        candidates = [issues[i] for i in ranked_hits(plant, issues)]
        results = await asyncio.gather(
            *(grade(grader, gap_prompt(GAP_CRITERION, plant, c, document, "analysis"), calls) for c in candidates)
        )
        best = max(range(len(results)), key=lambda k: results[k][0], default=None)
        if best is None or results[best][0] == 0.0:
            gaps.append(0.0)
            notes.append(f"{plant.id} gap_identified 0.0: " + ("nothing on its line" if best is None else gist(results[best][1])))
            continue
        gaps.append(results[best][0])
        notes += [f"{plant.id} gap_identified {results[best][0]}: {gist(results[best][1])}"] if results[best][0] < 1.0 else []
        named = candidates[best]
        if not (named.suggested_action or "").strip():
            actions.append(0.0)
            notes.append(f"{plant.id} action_repairs 0.0: no suggested action")
            continue
        value, why = await grade(grader, gap_prompt(REPAIR_CRITERION, plant, named, document, "suggested_action"), calls)
        actions.append(value)
        notes += [f"{plant.id} action_repairs {value}: {gist(why)}"] if value < 1.0 else []
    sound = await asyncio.gather(*(grade(grader, decoy_prompt(d, issues, document), calls) for d in inventory.decoys))
    notes += [f"{d.reason} sound_choices_respected {v}: {gist(why)}" for d, (v, why) in zip(inventory.decoys, sound) if v < 1.0]
    values = {
        "gap_identified": fraction(gaps),
        "action_repairs": fraction(actions),
        "sound_choices_respected": fraction([v for v, _ in sound]),
    }
    return values, " | ".join(notes) if notes else "all judged criteria passed"


@scorer(metrics=PER_KEY_METRICS)
def report_checks() -> Scorer:
    """The report's contract: the skill's five sections, web links, no informational issue."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            output = SimpleDeepAgentOutput.model_validate_json(state.output.completion)
        except ValueError as e:
            return Score(value={k: 0.0 for k in OWN_DESCRIPTIONS}, explanation=f"could not parse the workflow state: {e}")
        if output.result is None:
            return Score(value={k: 0.0 for k in OWN_DESCRIPTIONS}, explanation="no result in workflow state")
        values, explanation = report_scores(output.result.report_markdown or "", output.result.issues)
        return Score(value=values, explanation=explanation)

    return score


@scorer(metrics=PER_KEY_METRICS)
def plant_checks() -> Scorer:
    """Deterministic checks of the planted risks: an issue on each line, at a fitting severity."""
    return deterministic_scorer(plant_scores)


@scorer(metrics=PER_KEY_METRICS)
def methodology_judged(calls: int = 1) -> Scorer:
    """The graded criteria, on Inspect's ``grader`` role (the repo's default grader model when unset)."""

    async def score(state: TaskState, target: Target) -> Score:
        issues, error = issues_from_state(state)
        if error:
            return Score(value={k: 0.0 for k in JUDGED_KEYS}, explanation=error)
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        values, explanation = await judge_methodology(grader, issues, inventory_from_state(state), calls)
        return Score(value=values, explanation=explanation)

    return score


@task
def methodological_alignment_e2e(timeout_s: float = 900, judge_calls: int = 1) -> Task:
    """Run Methodological Alignment on every sample and score it against the planted risks.

    Args:
        timeout_s: How long to wait for one workflow run; web search makes this
            workflow slower than the document-only checks.
        judge_calls: Grader calls per graded item; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    columns = [
        *(("report_checks", k) for k in OWN_DESCRIPTIONS),
        *(("plant_checks", k) for k in PLANT_DESCRIPTIONS),
        *(("methodology_judged", k) for k in JUDGED_KEYS),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: planted methodological risks, anchored on the sentence stating the choice and carrying "
                "the labeller's account of what the field does instead (high severity where it undermines the "
                "main result); decoys are sound design choices, each with the labeller's reason. Other gaps the "
                "run reports are not scored. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "report_checks": OWN_DESCRIPTIONS,
                "plant_checks": PLANT_DESCRIPTIONS,
                "methodology_judged": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[report_checks(), plant_checks(), methodology_judged(calls=judge_calls)],
        fail_on_error=0.2,
        viewer=issue_viewer_config([], extra=columns, labels=SCORE_LABELS, issue_columns=False),
    )
