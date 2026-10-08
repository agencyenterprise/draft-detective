"""E2E eval for the Concision & Precision workflow.

Declared by ``skills/concision-precision/SKILL.md``; runs through the API like
every other e2e eval. Ground truth is ``dataset.yaml`` in inventory form:
the wordy, run-on, filler, vague, empty and obvious sentences a correct run
reports under six titles, anchored by verbatim quotes with edit expectations,
plus decoy sentences it must leave alone, one ``no_fp_<reason>`` metric per
exclusion the skill states (signposting, source qualifiers, hedges, compound
sentences joined by a comma and a conjunction, topic sentences that announce
specifics, first person, technical terms, precise long sentences, two clear
sentences, quoted wording, a named referent that only looks vague, a
framework's aims).

Scorers: the reusable ``issue_checks`` (detection and edit hygiene; several
expected sentences may share one reported issue, since wordy constructions
are reported once per paragraph) and ``decoy_checks``, this workflow's own
deterministic edit check (no passive introduced), and two judged criteria on
Inspect's model-grading protocol (``criteria.py``). A deletion is an edit with
an empty replacement.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/concision_precision/concision_precision_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.issue_checks import PER_KEY_METRICS, deterministic_scorer, extra_edit_scores
from evals_inspectai.e2e.concision_precision.criteria import (
    EXTRA_EDIT_CHECKS,
    EXTRA_EDIT_DESCRIPTIONS,
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "concision_precision"
DATASET = Path(__file__).parent / "dataset.yaml"
GROUND_TRUTH = (
    "Inventory: expected issues anchored by verbatim quotes, with edit expectations, plus decoy "
    "sentences that must not be flagged. A NaN metric value means the sample gave that check nothing to judge."
)
OWN_METRICS = {"concision_edit_checks": EXTRA_EDIT_DESCRIPTIONS, "judged_criteria": JUDGE_DESCRIPTIONS}


@scorer(metrics=PER_KEY_METRICS)
def concision_edit_checks() -> Scorer:
    """This workflow's own deterministic edit check: no passive introduced."""
    return deterministic_scorer(lambda issues, inventory: extra_edit_scores(issues, inventory, EXTRA_EDIT_CHECKS))


@task
def concision_precision_e2e(timeout_s: float = 1200, judge_calls: int = 1) -> Task:
    """Run Concision & Precision on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded edit; the median grade is kept.
    """
    suite = InventorySuite.load(DATASET)
    return Task(
        dataset=suite.dataset(),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[*suite.scorers(), concision_edit_checks(), suite.judged(JUDGE_CRITERIA, calls=judge_calls)],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, SCORE_LABELS),
    )
