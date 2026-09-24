"""E2E eval for the Recommendation Check workflow, on the issue-inventory structure.

The workflow reports one issue per recommendation occurrence, classified by
severity: ``none`` for supported, ``medium`` for partially supported, ``high``
for unsupported. Those titles paraphrase the recommendation, so the inventory
names no title for them: such an expected issue is detected when a reported
issue brackets its line (or quotes it), and the classification is read off
``severity_correct``. On top of them it reports three kinds with fixed titles
(RAND EEI item 8): "Recommendation Not Actionable", "Recommendation Audience
Unclear" and "Too Many Recommendations". Those are named in the inventory, so
``title_correct`` is scored for them, and titled decoys mark recommendations
that must not be reported under a given kind.
It proposes no edits, and the inventory says nothing about edits, so
``issue_checks`` runs without its edit-hygiene keys.

Scorers:

- ``issue_checks``: recall, precision, F0.5 over the expected issues, the clean
  document left alone, and title, severity and anchor line per covered issue.
  One reported issue covers at most one expected issue (``one_to_one``), since
  the skill requires each occurrence, including a restatement, to be reported
  separately and the new kinds as issues of their own; a run that merges two
  loses recall on the second. An issue under one of the fixed titles is paired
  with a support expectation only when no free-form report of that
  recommendation exists (``hit_tier``), so an extra actionability or audience
  issue on the same line costs precision and cannot stand in for the support
  verdict.
- ``decoy_checks``: sentences that read like recommendations but are not
  (conclusions restating findings), and recommendations that must not get a
  given kind, by reason: no unclear audience where a lead-in or heading names
  who acts or the document is about a single evident actor's own work; no
  not-actionable issue on a concrete action, one left without a number, or a
  hedged but concrete one; no length issue on a list of three or fewer, on
  restatements of the same recommendations, or on sub-items of one.
- ``tool_called("view_image")``: on the two samples whose finding is only in a
  chart, whether the agent looked at it.
- ``judged_criteria``: whether the suggested action of each new-kind issue is
  usable (``criteria.py``).

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/recommendation_check/recommendation_check_e2e.py --epochs 3
    uv run inspect eval evals_inspectai/e2e/recommendation_check/recommendation_check_e2e.py -T judge_calls=3
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    EDIT_DESCRIPTIONS,
    decoy_checks,
    decoy_descriptions,
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
from evals_inspectai.common.scorers import tool_called
from evals_inspectai.e2e.recommendation_check.criteria import JUDGE_CRITERIA, JUDGE_DESCRIPTIONS, SCORE_LABELS

WORKFLOW_TYPE = "recommendation_check"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def recommendation_check_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Recommendation Check on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    edits, titles = expects_edits(records), expects_titles(records)
    keys = issue_check_keys(edits, titles)
    extra = [("tool_called", "tool_called"), *(("judged_criteria", c.key) for c in JUDGE_CRITERIA)]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per recommendation occurrence, anchored by its wording, "
                "with the severity its classification maps to (none / medium / high) and a free-form title; "
                "plus one per not-actionable recommendation, unclear audience and over-long list, under "
                "their fixed titles. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in {**DETECTION_DESCRIPTIONS, **EDIT_DESCRIPTIONS}.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "tool_called": {"tool_called": "On a sample whose document embeds a chart, whether the agent called view_image."},
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=edits, one_to_one=True, titles=titles),
            decoy_checks(reasons),
            tool_called("view_image"),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            reasons, edits, extra=extra, labels={"tool_called": "Viewed image", **SCORE_LABELS}, titles=titles
        ),
    )
