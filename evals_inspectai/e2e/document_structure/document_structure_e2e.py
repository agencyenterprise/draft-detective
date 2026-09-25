"""E2E eval for the Document Structure (Document Contents) workflow, on the issue-inventory structure.

The workflow reports one "Missing Section: <name>" issue per required section
the document lacks (and for an appendix the body references but the document
does not contain). Every such issue is about something absent, so no expected
issue has an anchor: each is matched on its title alone, and the line-range
check is not emitted.

Scorers:

- ``issue_checks``: recall and precision over the missing sections and the
  clean document left alone. The skill sets no severity, so none is checked.
  One reported issue covers at most one missing section (``one_to_one``).
- ``model_graded_check``: the free-text ``target_answer`` per sample, graded
  C / P / I.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/document_structure/document_structure_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import DETECTION_DESCRIPTIONS, issue_check_keys, issue_checks
from evals_inspectai.common.issue_inventory import (
    expects_anchors,
    expects_severities,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import model_graded_check

WORKFLOW_TYPE = "document_structure"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def document_structure_e2e(timeout_s: float = 300) -> Task:
    """Run Document Structure on every sample and score it against the inventory."""
    records = load_inventory_records(DATASET)
    anchors, severities = expects_anchors(records), expects_severities(records)
    keys = issue_check_keys(edits=False, anchors=anchors, severities=severities)
    judge = ("model_graded_check", "model_graded_check")
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per missing section, matched on its 'Missing Section: <name>' title "
                "(no anchor, since the section is absent); clean documents expect none. A NaN metric value means "
                "the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "model_graded_check": {"model_graded_check": "The sample's target_answer, graded C / P / I by the grader model."},
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=False, one_to_one=True, anchors=anchors, severities=severities),
            model_graded_check(partial_credit=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            [],
            edits=False,
            extra=[judge],
            labels={"model_graded_check": "Judge"},
            anchors=anchors,
            severities=severities,
        ),
    )
