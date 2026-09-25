"""E2E eval for the Advocacy & Tone v2 workflow, on the issue-inventory structure.

The workflow emits one issue per genuine occurrence, bracketing the offending
sentence, under a stable title per check ("Trigger Words Detected", "Advocacy
Language Detected", "Subjective Tone Detected") and the severity the skill
gives that check. Each sample swaps one Findings sentence into the same short
report, so the inventory expects one issue on that sentence (positive samples)
or none at all (clean samples, whose Findings sentence is a decoy when it holds
a word the skill must leave alone in that context).

Scorers:

- ``issue_checks``: recall, precision, F0.5, the clean document left alone,
  title and severity per covered issue, and whether the issue brackets the
  sentence. One reported issue covers at most one expected (``one_to_one``),
  since the skill reports each occurrence separately. A false positive under
  any title costs precision, not only under the title a sample is about.
- ``decoy_checks``: which carve-out misfired, by decoy reason.
- ``model_graded_check``: the free-text ``target_answer`` per sample, graded
  C / P / I.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/advocacy_tone_v2/advocacy_tone_v2_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    decoy_checks,
    decoy_descriptions,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import decoy_reasons, inventory_dataset, load_inventory_records
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import model_graded_check

WORKFLOW_TYPE = "advocacy_tone_v2"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def advocacy_tone_v2_e2e(timeout_s: float = 600) -> Task:
    """Run Advocacy & Tone v2 on every sample and score it against the inventory."""
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    keys = issue_check_keys(edits=False)
    judge = ("model_graded_check", "model_graded_check")
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per flagged Findings sentence, with the check's title and severity; "
                "clean documents expect none, and a Findings sentence the skill must leave alone is a decoy tagged "
                "with its carve-out. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "model_graded_check": {"model_graded_check": "The sample's target_answer, graded C / P / I by the grader model."},
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=False, one_to_one=True),
            decoy_checks(reasons),
            model_graded_check(partial_credit=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=False, extra=[judge], labels={"model_graded_check": "Judge"}),
    )
