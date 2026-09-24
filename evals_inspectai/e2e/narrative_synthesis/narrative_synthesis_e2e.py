"""E2E eval for the Narrative & Synthesis workflow.

Declared by ``skills/narrative-synthesis/SKILL.md``; runs through the API like
every other e2e eval. Ground truth is ``dataset.yaml`` in inventory form: the
data dumps, order problems, unanswered framing questions and restated points a
correct run reports, each anchored where the skill anchors it (order, why it
matters and what is new on the introductory section, what happens next on the
concluding or last section), plus decoys for every exclusion the skill states
(data interpreted in place or at the start of the next paragraph, a single
comparison, a single statistic that makes its point, tables and the sentence
pointing to them, methods numbers, appendix data, summaries by design, brief
references back, signposting, framing answered in a summary instead of the
introduction, headers that belong to the header check).

The skill proposes no edits, so ``issue_checks`` runs without its edit-hygiene
keys. Each finding is one issue (one per passage, one per framing question, one
for order), so matching is ``one_to_one``: the two framing questions a report
misses are anchored on the same paragraph and must be reported separately.
Scorers: the reusable ``issue_checks`` and ``decoy_checks``, this workflow's own
deterministic check (no issue cites a rule), and two judged criteria on the
suggested actions.

Not covered: the main body's length (the threshold needs a document of about
15,000 words; see the ``ns-devsplit`` note in ``docs/eval-scores.md``) and the
volume cap, since no record has more than five data dumps or restated points.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/narrative_synthesis/narrative_synthesis_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    PER_KEY_METRICS,
    decoy_checks,
    decoy_descriptions,
    deterministic_scorer,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_edits,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.e2e.narrative_synthesis.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    rule_reference_scores,
)

WORKFLOW_TYPE = "narrative_synthesis"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def narrative_checks() -> Scorer:
    """This workflow's own deterministic check: no issue cites a rule or guideline."""
    return deterministic_scorer(rule_reference_scores)


@task
def narrative_synthesis_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Narrative & Synthesis on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    edits = expects_edits(records)
    keys = issue_check_keys(edits)
    own = [
        *(("narrative_checks", key) for key in OWN_DESCRIPTIONS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per data dump, restated point, unanswered framing question and "
                "order problem, anchored where the skill anchors it, plus decoy sentences that must not be flagged. "
                "No edits are expected. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "narrative_checks": OWN_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=edits, one_to_one=True),
            decoy_checks(reasons),
            narrative_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits, extra=own, labels=SCORE_LABELS),
    )
