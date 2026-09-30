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
from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.source_citations import source_checks
from evals_inspectai.e2e.live_reports_v2.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "live_reports_v2"
DATASET = Path(__file__).parent / "dataset.yaml"
GROUND_TRUTH = (
    "Inventory: one expected issue per claim later evidence overturned or updated, anchored on the "
    "claim and carrying the labeller's account of what changed; documents with no such claim expect "
    "none. Any number of issues may cover a claim. Decoys are sentences newer research cannot update. "
    "Severity is not checked and no edits are expected. A NaN metric value means the sample gave "
    "that check nothing to judge."
)
OWN_METRICS = {"source_checks": OWN_DESCRIPTIONS, "judged_criteria": JUDGE_DESCRIPTIONS}


@task
def live_reports_v2_e2e(timeout_s: float = 1800, judge_calls: int = 1) -> Task:
    """Run Live Reports on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    suite = InventorySuite.load(DATASET, pairing="several_per_expected")
    return Task(
        dataset=suite.dataset(),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=api_workflow_solver(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            *suite.scorers(),
            source_checks(after=True, new_sources_only=True),
            suite.judged(JUDGE_CRITERIA, calls=judge_calls),
        ],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, SCORE_LABELS),
    )
