"""E2E eval for the Figures & Tables Check workflow, on the issue-inventory structure.

The workflow reports one issue per failed rule and element: "Figure/Table
Missing Title: <label>", "Unreferenced Figure/Table: <label>", "Missing
Figure/Table: <label>" and "Inconsistent Numbering: <description>". The
inventory matches each on the stable, rule-naming part of its title, anchors an
issue about one element where that element sits, and leaves numbering issues
(which concern the whole sequence) unanchored.

Scorers:

- ``issue_checks``: recall, precision, F0.5, the clean document left alone,
  the rule named in the title and whether the issue brackets the element. One
  reported issue covers at most one expected (``one_to_one``), since the skill
  reports one issue per offending element. The skill sets no severity, so
  none is checked.
- ``decoy_checks``: elements a correct run leaves alone (an abbreviation
  table, appendix- or chapter-prefixed numbering, a figure cited in the body),
  by the rule exception that applies.
- ``model_graded_check``: the free-text ``target_answer`` per sample, graded
  C / P / I.
- ``tool_called("view_image")``: on the samples whose document embeds a
  figure, whether the agent looked at it.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --epochs 3
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
from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_severities,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import model_graded_check, tool_called

WORKFLOW_TYPE = "figures_tables_check"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def figures_tables_check_e2e(timeout_s: float = 600) -> Task:
    """Run Figures & Tables Check on every sample and score it against the inventory."""
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    severities = expects_severities(records)
    keys = issue_check_keys(edits=False, severities=severities)
    judge = ("model_graded_check", "model_graded_check")
    image_check = ("tool_called", "tool_called")
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per offending element, matched on the rule its title names and "
                "anchored where the element sits; numbering issues are matched on 'Inconsistent Numbering' alone. "
                "Clean documents expect none; decoys are elements a correct run leaves alone. A NaN metric value "
                "means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "model_graded_check": {"model_graded_check": "The sample's target_answer, graded C / P / I by the grader model."},
                "tool_called": {"tool_called": "On a sample whose document embeds a figure, whether the agent called view_image."},
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=False, one_to_one=True, severities=severities),
            decoy_checks(reasons),
            model_graded_check(partial_credit=True),
            tool_called("view_image"),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            reasons,
            edits=False,
            extra=[judge, image_check],
            labels={"model_graded_check": "Judge", "tool_called": "Viewed image"},
            severities=severities,
        ),
    )
