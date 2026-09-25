"""E2E eval for the About This (GER) workflow, on the issue-inventory structure.

The workflow runs two validators, one on the preface and one on the author
biographies, and keeps each one's issues in its own state field
(``preface_result``, ``authors_result``). The eval reads both together: the
titles already say which validator an issue came from. A failed preface rule
is about something the preface lacks, so its expected issue has no anchor and
is matched on its title; an author issue is anchored on the bio it is about.

Scorers:

- ``issue_checks``: recall, precision, F0.5, the clean document left alone,
  severity, and for author issues the title and whether the issue brackets
  the bio. Every sample breaks at most one rule, so the skill's allowance to
  split or combine one author's failed rules never changes the expected
  count; one reported issue covers at most one expected (``one_to_one``).
- ``model_graded_check``: the free-text ``target_answer`` per sample, graded
  C / P / I.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/about_this_ger/about_this_ger_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import DETECTION_DESCRIPTIONS, issue_check_keys, issue_checks
from evals_inspectai.common.issue_inventory import inventory_dataset, load_inventory_records
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import model_graded_check

WORKFLOW_TYPE = "about_this_ger"
DATASET = Path(__file__).parent / "dataset.yaml"
# The state fields holding each validator's AgentCheckResult.
RESULTS = ("preface_result", "authors_result")


@task
def about_this_ger_e2e(timeout_s: float = 600) -> Task:
    """Run About This (GER) on every sample and score both validators against the inventory."""
    records = load_inventory_records(DATASET)
    keys = issue_check_keys(edits=False)
    judge = ("model_graded_check", "model_graded_check")
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per broken rule, across both validators. Preface rules and missing "
                "sections are matched on their title (no anchor, since the content is absent); author issues are "
                "anchored on the bio. The seed document expects none. A NaN metric value means the sample gave "
                "that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "model_graded_check": {"model_graded_check": "The sample's target_answer, graded C / P / I by the grader model."},
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s, item_messages_key="agent_conversations"),
        scorer=[
            issue_checks(edits=False, one_to_one=True, results=RESULTS),
            model_graded_check(partial_credit=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config([], edits=False, extra=[judge], labels={"model_graded_check": "Judge"}),
    )
