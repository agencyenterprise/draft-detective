"""E2E eval for the Writing Consistency workflow.

Declared by ``skills/writing-consistency/SKILL.md``; runs through the API like
every other e2e eval. Ground truth is ``dataset.yaml`` in inventory form: the
inconsistent terms, spellings, tenses, tones and house-style compounds a
correct run reports, one issue per inconsistency anchored at the first
minority occurrence, plus decoys, one ``no_fp_<reason>`` metric per
legitimate variation the skill must leave alone (different names for
different things, a term glossed then shortened, a compound open after a verb
and hyphenated before a noun, singular against plural, quoted wording and
titles, tables with their own number conventions, present tense for general
truths, signposting and interpretation, proper names, a sentence already in
the document's settled form).

Titles carry the variants after a colon (``Inconsistent Term: form A / form
B``), so the inventory names the stable prefix, matched as whole words within
the reported title; a pair that could fairly be called spelling or number
style names the bare prefix ``Inconsistent``. Phrases expected of an edit are
read off the line with all of the issue's edits applied, since these edits
swap single words. Scorers: the reusable ``issue_checks`` and
``decoy_checks``, this workflow's own deterministic edit check (the edit
changes only the variant), and one judged criterion.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/writing_consistency/writing_consistency_e2e.py --epochs 3
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
from evals_inspectai.e2e.writing_consistency.criteria import (
    EXTRA_EDIT_CHECKS,
    EXTRA_EDIT_DESCRIPTIONS,
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "writing_consistency"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def consistency_edit_checks() -> Scorer:
    """This workflow's own deterministic edit check: the edit changes only the variant."""
    return deterministic_scorer(lambda issues, inventory: extra_edit_scores(issues, inventory, EXTRA_EDIT_CHECKS))


@task
def writing_consistency_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Writing Consistency on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded edit; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    own = [
        *(("consistency_edit_checks", f"edit_{name}") for name in EXTRA_EDIT_CHECKS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per inconsistency, anchored at the first minority occurrence, with "
                "edit expectations, plus decoy sentences whose variation is legitimate. A NaN metric value means the "
                "sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {**DETECTION_DESCRIPTIONS, **EDIT_DESCRIPTIONS},
                "decoy_checks": decoy_descriptions(reasons),
                "consistency_edit_checks": EXTRA_EDIT_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(),
            decoy_checks(reasons),
            consistency_edit_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=True, extra=own, labels=SCORE_LABELS),
    )
