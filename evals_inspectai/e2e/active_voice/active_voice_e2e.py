"""E2E eval for the Active Voice & Clear Actors workflow.

The workflow is declared by its skill (``skills/active-voice/SKILL.md``) and
runs through the API like every other e2e eval. Ground truth is ``dataset.yaml``
in inventory form: the issues a correct run reports, anchored by verbatim
quotes and with edit expectations, plus decoy sentences it must leave alone
(``evals_inspectai/common/issue_inventory.py``).

Four scorers, all dict-valued so every check is its own metric, and kept
separate because their key sets have different owners. Three are reusable
scorers from ``evals_inspectai/common`` that this module only composes:

- ``issue_checks`` (``issue_checks.py``): detection and edit hygiene; the same
  keys for every issue-inventory eval.
- ``decoy_checks`` (``issue_checks.py``): false positives by reason; keys follow
  this dataset's decoys, one per exclusion rule the skill states (stative
  participle, generic actor, idiom, participial modifier, source qualifier or
  definition, quoted wording, excluded material, a sentence whose point is the
  actor, an already-active sentence).
- ``judged_criteria`` (``issue_judge.py``): graded criteria, one grader call per
  edit or issue on Inspect's model-grading protocol; the criteria come from
  ``criteria.py``.
- ``active_voice_edit_checks`` (defined here): this workflow's own deterministic
  edit check, that an edit removes the passive (``criteria.py``).

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_e2e.py
    uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_e2e.py --epochs 3 --epochs-reducer at_least_3
    uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_e2e.py -T judge_calls=3 --model-role grader=openai/gpt-5.4
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
from evals_inspectai.e2e.active_voice.criteria import (
    EXTRA_EDIT_CHECKS,
    EXTRA_EDIT_DESCRIPTIONS,
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
)
from evals_inspectai.e2e.active_voice.viewer import viewer_config

WORKFLOW_TYPE = "active_voice"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def active_voice_edit_checks() -> Scorer:
    """This workflow's own deterministic edit check: the passive is gone."""
    return deterministic_scorer(lambda issues, inventory: extra_edit_scores(issues, inventory, EXTRA_EDIT_CHECKS))


def metric_descriptions(reasons: list[str]) -> dict[str, dict[str, str]]:
    """What each metric checks, per scorer: stored as Task metadata so the log
    viewer's Info tab explains the columns. Score explanations stay per sample."""
    return {
        "issue_checks": {**DETECTION_DESCRIPTIONS, **EDIT_DESCRIPTIONS},
        "decoy_checks": decoy_descriptions(reasons),
        "active_voice_edit_checks": EXTRA_EDIT_DESCRIPTIONS,
        "judged_criteria": JUDGE_DESCRIPTIONS,
    }


@task
def active_voice_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run the Active Voice workflow on every sample and score it.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded item (each edit, each unknown-actor
            issue) in ``judged_criteria``; the median grade is kept. 1 is one
            call. Use 3 when a criterion's grader disagrees with itself run to
            run, at three times the grading cost (``-T judge_calls=3``).
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": "Inventory: expected issues anchored by verbatim quotes, with edit expectations, plus decoy sentences that must not be flagged. A NaN metric value means the sample gave that check nothing to judge.",
            "metrics": metric_descriptions(reasons),
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(),
            decoy_checks(reasons),
            active_voice_edit_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls),
        ],
        fail_on_error=0.2,
        viewer=viewer_config(reasons),
    )
