"""E2E eval for the Concision & Precision workflow.

Declared by ``skills/concision-precision/SKILL.md``; runs through the API like
every other e2e eval. Ground truth is ``dataset.yaml`` in inventory form:
the wordy, run-on, filler, vague, empty and obvious sentences a correct run
reports, anchored by verbatim quotes with edit expectations, plus decoy
sentences it must leave alone (signposting, source qualifiers, hedges, two
clear sentences, precise long sentences).

Scorers: the reusable ``issue_checks`` and ``decoy_checks``, this workflow's
own deterministic edit check (no passive introduced), and two judged criteria
on Inspect's model-grading protocol (``criteria.py``).

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/concision_precision/concision_precision_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    EDIT_DESCRIPTIONS,
    PER_KEY_METRICS,
    decoy_checks,
    decoy_descriptions,
    deterministic_scorer,
    extra_edit_scores,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import decoy_reasons, inventory_dataset, load_inventory_records
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.e2e.concision_precision.criteria import (
    EXTRA_EDIT_CHECKS,
    EXTRA_EDIT_DESCRIPTIONS,
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "concision_precision"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def concision_edit_checks() -> Scorer:
    """This workflow's own deterministic edit check: no passive introduced."""
    return deterministic_scorer(lambda issues, inventory: extra_edit_scores(issues, inventory, EXTRA_EDIT_CHECKS))


@task
def concision_precision_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Concision & Precision on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded edit; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    own = [
        *(("concision_edit_checks", f"edit_{name}") for name in EXTRA_EDIT_CHECKS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: expected issues anchored by verbatim quotes, with edit expectations, plus decoy "
                "sentences that must not be flagged. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {**DETECTION_DESCRIPTIONS, **EDIT_DESCRIPTIONS},
                "decoy_checks": decoy_descriptions(reasons),
                "concision_edit_checks": EXTRA_EDIT_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(),
            decoy_checks(reasons),
            concision_edit_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=True, extra=own, labels=SCORE_LABELS),
    )
