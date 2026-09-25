"""E2E eval for the Advocacy & Tone v2 workflow, on the issue-inventory structure.

Declared by ``skills/advocacy-tone/SKILL.md``; runs through the API like every
other e2e eval. The workflow emits one issue per genuine occurrence, bracketing
the offending sentence, under a fixed title per kind ("Trigger Words Detected",
"Advocacy Language Detected", "Subjective Tone Detected") with the severity the
skill gives that kind (low, medium, medium).

Ground truth is ``dataset.yaml``: fourteen copies of one short report with a
single Findings sentence swapped (one positive per listed word class, and the
skill's own do-not-flag examples), then longer multi-section reports with
several findings of different kinds each: every trigger word and advocacy
phrase in context, "the policy clearly states X" beside "X is clearly the best
approach", the authors' own "must" and "critical" in a Recommendations section
beside a quoted statute and an evidence-based recommendation, subjective tone
with no listed word, hedged claims, listed words used descriptively ("had never
visited"), matches under Acknowledgments, About the Authors, References,
Bibliography and Appendix headings, and fully clean reports. A sentence that
fairly reads as a second kind carries that kind as an optional expected issue.

Scorers: the reusable ``issue_checks`` (severity included) and ``decoy_checks``
(which carve-out misfired), this workflow's own deterministic ``tone_checks``
over every reported issue (known title, severity that follows the title, a
one-line range, nothing in a skipped section), and two judged criteria on the
suggested action (concrete, and faithful to the sentence). Each occurrence is
its own issue, so matching is ``one_to_one``; a false positive under any title
costs precision.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/advocacy_tone_v2/advocacy_tone_v2_e2e.py --epochs 3
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
from evals_inspectai.e2e.advocacy_tone_v2.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    tone_scores,
)

WORKFLOW_TYPE = "advocacy_tone_v2"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def tone_checks() -> Scorer:
    """This workflow's own deterministic checks over every reported issue."""
    return deterministic_scorer(tone_scores)


@task
def advocacy_tone_v2_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Advocacy & Tone v2 on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    edits = expects_edits(records)
    keys = issue_check_keys(edits=edits)
    own = [
        *(("tone_checks", key) for key in OWN_DESCRIPTIONS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per flagged sentence, with its kind's title and severity (a second "
                "kind a sentence fairly reads as is optional); clean documents expect none, and a sentence the skill "
                "must leave alone is a decoy tagged with its carve-out. No edits are expected. A NaN metric value "
                "means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "tone_checks": OWN_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=edits, one_to_one=True),
            decoy_checks(reasons),
            tone_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=edits, extra=own, labels=SCORE_LABELS),
    )
