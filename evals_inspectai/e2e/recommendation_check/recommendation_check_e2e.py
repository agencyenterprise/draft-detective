"""E2E eval for the Recommendation Check workflow, on the issue-inventory structure.

The workflow reports one issue per recommendation occurrence, classified by
severity: ``none`` for supported, ``medium`` for partially supported, ``high``
for unsupported. Its titles paraphrase the recommendation, so the inventory
names no title: an expected issue is detected when a reported issue brackets
its line (or quotes it), and the classification is read off ``severity_correct``.
It proposes no edits, and the inventory says nothing about edits, so
``issue_checks`` runs without its edit-hygiene keys.

Scorers, all reusable from ``evals_inspectai/common``:

- ``issue_checks``: recall, precision, F0.5 over the recommendations, the clean
  document left alone, and severity per covered recommendation. One reported
  issue covers at most one recommendation (``one_to_one``), since the skill
  requires each occurrence, including a restatement, to be reported separately;
  a run that merges two loses recall on the second.
- ``decoy_checks``: sentences that read like recommendations but are not
  (conclusions restating findings), by reason.
- ``tool_called("view_image")``: on the two samples whose finding is only in a
  chart, whether the agent looked at it.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/recommendation_check/recommendation_check_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    EDIT_DESCRIPTIONS,
    decoy_checks,
    decoy_descriptions,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_edits,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import tool_called

WORKFLOW_TYPE = "recommendation_check"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def recommendation_check_e2e(timeout_s: float = 600) -> Task:
    """Run Recommendation Check on every sample and score it against the inventory."""
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    edits = expects_edits(records)
    image_check = ("tool_called", "tool_called")
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per recommendation occurrence, anchored by its wording, "
                "with the severity its classification maps to (none / medium / high). Titles are free-form "
                "and not scored. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {**DETECTION_DESCRIPTIONS, **(EDIT_DESCRIPTIONS if edits else {})},
                "decoy_checks": decoy_descriptions(reasons),
                "tool_called": {"tool_called": "On a sample whose document embeds a chart, whether the agent called view_image."},
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[issue_checks(edits=edits, one_to_one=True), decoy_checks(reasons), tool_called("view_image")],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits, extra=[image_check], labels={"tool_called": "Viewed image"}),
    )
