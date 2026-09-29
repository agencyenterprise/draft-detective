"""E2E eval for the Live Reports workflow, on the issue-inventory structure.

Declared by ``skills/live-reports/SKILL.md``; runs through the API like every
other e2e eval. The workflow searches the web for literature published after
the document's publication date that updates or challenges its claims, and
reports one issue per claim to update, anchored at the claim.

Ground truth is ``dataset.yaml``: dated documents whose claims later evidence
overturned (a superseded standard, a reversed guideline, a broken record),
optional claims that still hold and may get supporting evidence, and decoys
newer research cannot update (historical facts, local facts, procedure). Two
documents make no claim at all. Every record sets the publication date, which
the shared ``api_workflow_solver`` puts on the project.

Scorers: the reusable ``issue_checks`` and ``decoy_checks`` (titles are
free-form, so matching is on the anchor quoted or its line bracketed; severity
is not checked), the shared ``source_checks`` (a findable citation, dated no
earlier than the document, listed in the report, not already in the
document's references), and two judged criteria (the evidence is what changed
the claim; the action says how to revise it). Several issues may cover one
claim: with ``several_per_expected`` each counts toward precision and each is
judged.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/live_reports_v2/live_reports_v2_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_solver
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    decoy_checks,
    decoy_descriptions,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import decoy_reasons, inventory_dataset, load_inventory_records
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.source_citations import source_checks
from evals_inspectai.e2e.live_reports_v2.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "live_reports_v2"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def live_reports_v2_e2e(timeout_s: float = 1800, judge_calls: int = 1) -> Task:
    """Run Live Reports on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    keys = issue_check_keys(edits=False, titles=False, severities=False)
    own = [
        *(("source_checks", key) for key in OWN_DESCRIPTIONS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per claim later evidence overturned or updated, anchored on the "
                "claim and carrying the labeller's account of what changed; documents with no such claim expect "
                "none. Any number of issues may cover a claim. Decoys are sentences newer research cannot update. "
                "Severity is not checked and no edits are expected. A NaN metric value means the sample gave "
                "that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "source_checks": OWN_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_solver(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=False, titles=False, severities=False, several_per_expected=True),
            decoy_checks(reasons),
            source_checks(after=True, new_sources_only=True),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, several_per_expected=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=False, extra=own, labels=SCORE_LABELS, titles=False, severities=False),
    )
