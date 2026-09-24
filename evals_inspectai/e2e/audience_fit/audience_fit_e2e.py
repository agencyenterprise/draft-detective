"""E2E eval for the Audience Fit workflow.

Declared by ``skills/audience-fit/SKILL.md``; runs through the API like every
other e2e eval. Ground truth is ``dataset.yaml`` in inventory form: the
audience problems (missing, too vague, conflicting) and the paragraphs or
passages of technical language a correct run reports, plus decoys (a specific
or merely reworded audience, a technical audience, the audience's own
vocabulary, plain method and number descriptions, terms explained in place,
appendix content and pointers, quoted wording).

The workflow proposes no edits, so the edit-hygiene keys are left out. Each
audience issue is reported once per document and each technical paragraph
once, so a reported issue covers at most one expected issue (``one_to_one``).
Scorers: the reusable ``issue_checks`` and ``decoy_checks``, this workflow's
own ``overflow_checks`` on the cap of technical-language issues, and two
judged criteria on the suggested action.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/audience_fit/audience_fit_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    PER_KEY_METRICS,
    decoy_checks,
    decoy_descriptions,
    deterministic_scorer,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_edits,
    expects_titles,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.e2e.audience_fit.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    SCORE_LABELS,
)
from evals_inspectai.e2e.audience_fit.overflow import (
    OVERFLOW_DESCRIPTIONS,
    OVERFLOW_KEYS,
    OVERFLOW_LABELS,
    overflow_scores,
)

WORKFLOW_TYPE = "audience_fit"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def overflow_checks() -> Scorer:
    """This workflow's own deterministic check: the cap on technical-language issues and its summary."""
    return deterministic_scorer(overflow_scores)


@task
def audience_fit_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Audience Fit on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    edits, titles = expects_edits(records), expects_titles(records)
    keys = issue_check_keys(edits, titles)
    own = [
        *(("overflow_checks", key) for key in OVERFLOW_KEYS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per audience problem and per paragraph or passage of technical "
                "language, anchored by a sentence in it, plus decoy sentences the check must leave alone. No edits "
                "are expected. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {
                    k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys
                },
                "decoy_checks": decoy_descriptions(reasons),
                "overflow_checks": OVERFLOW_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=edits, one_to_one=True, titles=titles),
            decoy_checks(reasons),
            overflow_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            reasons,
            edits,
            extra=own,
            labels={**SCORE_LABELS, **OVERFLOW_LABELS},
            titles=titles,
        ),
    )
