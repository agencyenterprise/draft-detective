"""E2E eval for the Literature Review workflow, on the issue-inventory structure.

Declared by ``skills/literature-review/SKILL.md``; runs through the API like
every other e2e eval. The workflow searches the web for sources the document
should cite or discuss, both supporting and conflicting, and reports one issue
per recommended source, anchored at the claim it relates to.

Ground truth is ``dataset.yaml``: claims that need sources (well-studied
claims left uncited, one-sided claims with a known conflicting literature, a
claim a reference already in the bibliography supports but is never cited
for), optional claims a run may reasonably add to, and decoys no source is
needed for (the document's own data, local facts, procedure). Two documents
make no claim at all. Several records set a publication date, so the run may
recommend only what the authors could have cited.

Scorers: the reusable ``issue_checks`` and ``decoy_checks`` (titles are
free-form, so matching is on the anchor quoted or its line bracketed; severity
is not checked), the shared ``source_checks`` (a findable citation, dated
before the publication date, listed in the report), and two judged criteria
(the source bears on the claim; the action says what to do with it). One issue
is reported per source, so several may cover one claim: with
``several_per_expected`` each of them counts toward precision and each is
judged, not only the one paired with the claim.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/literature_review_v2/literature_review_v2_e2e.py --epochs 3
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
from evals_inspectai.e2e.literature_review_v2.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "literature_review_v2"
DATASET = Path(__file__).parent / "dataset.yaml"


@task
def literature_review_v2_e2e(timeout_s: float = 1200, judge_calls: int = 1) -> Task:
    """Run Literature Review on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API; the
            web-search agent's own per-call timeout is already 600s.
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
                "Inventory: one expected issue per claim that needs a source, anchored on the claim and carrying "
                "the labeller's account of the literature it should engage with; documents with no claim expect "
                "none. Any number of issues may cover a claim. Decoys are sentences no source is needed for. "
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
            source_checks(after=False, new_sources_only=False),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, several_per_expected=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=False, extra=own, labels=SCORE_LABELS, titles=False, severities=False),
    )
