"""E2E eval for the Headers & Skimmability workflow.

Declared by ``skills/headers-skimmability/SKILL.md``; runs through the API like
every other e2e eval. Ground truth is ``dataset.yaml`` in inventory form: one
expected issue per vague, takeaway-less or mismatched header, per topic-label
bold opener, per long key finding and overlong key findings box, and one per
document whose opening never states its bottom line, plus decoys for every
exclusion the skill states (procedural and protected headers, headers naming
the alternatives an assessment compares, headers readers look for by name,
the document title, signposting, procedural bold labels, bold emphasis,
openers that argue). Header anchors are the header text, with an explicit
line where that text recurs in the prose.

The workflow proposes no edits, so ``issue_checks`` runs without the edit
hygiene keys; each header is its own issue, so it pairs one to one. The
suggested header wording lives in the suggested action, which this workflow's
own deterministic checks read back and the judge grades against the section it
heads.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/headers_skimmability/headers_skimmability_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.issue_checks import PER_KEY_METRICS, deterministic_scorer
from evals_inspectai.e2e.headers_skimmability.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    SCORE_LABELS,
    SUGGESTION_DESCRIPTIONS,
    suggestion_scores,
)

WORKFLOW_TYPE = "headers_skimmability"
DATASET = Path(__file__).parent / "dataset.yaml"
GROUND_TRUTH = (
    "Inventory: one expected issue per weak header, topic-label lead sentence, long key finding or "
    "overlong key findings box, and per document without a bottom line up front, plus decoys for each "
    "exclusion the skill states. No edits are expected. A NaN metric value means the sample gave that "
    "check nothing to judge."
)
OWN_METRICS = {"suggestion_checks": SUGGESTION_DESCRIPTIONS, "judged_criteria": JUDGE_DESCRIPTIONS}


@scorer(metrics=PER_KEY_METRICS)
def suggestion_checks() -> Scorer:
    """This workflow's own deterministic checks on the suggested header and lead wording."""
    return deterministic_scorer(suggestion_scores)


@task
def headers_skimmability_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Headers & Skimmability on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    suite = InventorySuite.load(DATASET, pairing="one_to_one")
    return Task(
        dataset=suite.dataset(),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[*suite.scorers(), suggestion_checks(), suite.judged(JUDGE_CRITERIA, calls=judge_calls)],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, SCORE_LABELS),
    )
