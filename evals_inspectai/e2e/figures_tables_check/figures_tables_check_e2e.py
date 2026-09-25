"""E2E eval for the Figures & Tables Check workflow, on the issue-inventory structure.

Declared by ``skills/figures-tables-check/SKILL.md``; runs through the API like
every other e2e eval. The workflow reports one issue per failed rule and
element: "Figure/Table Missing Title: <label>", "Unreferenced Figure/Table:
<label>", "Missing Figure/Table: <label>" and "Inconsistent Numbering:
<description>". The inventory matches each on the rule part of its title,
anchors an issue about one element where that element sits (its caption, or
the body sentence citing a missing one), and leaves numbering issues, which
concern the whole sequence, unanchored.

Ground truth is ``dataset.yaml``: clean documents (sequential, by-chapter and
appendix-prefixed numbering, supplementary S-numbering, "Fig." abbreviations,
parenthetical and plural references, no exhibits at all, two published
reports); every rule failing on its own, with label variants (a bare
"Figure 2:" or "**Table 2**", an unlabelled table, a captioned figure with no
number, a table cited only inside another caption, a missing "Fig. 3" or
"Table S2"); every numbering branch (a skip, a repeat, an arbitrary 3.1 in a
flat report, an appendix or chapter prefix that does not match its section);
documents failing several rules at once; decoys for the exclusions
(abbreviation and acronym tables, valid prefixes, the references the skill
counts); and embedded images (a decorative logo, a caption inside the image, a
placeholder box, a chart with no caption).

Scorers:

- ``issue_checks``: recall, precision, F0.5, the clean document left alone,
  the rule named in the title, whether the issue brackets the element, and
  severity where the issues skill fixes it (a missing figure or table is an
  unresolvable reference, high; an unreferenced element and inconsistent
  numbering are medium; a missing title is left unchecked, since the scale
  does not place it). One reported issue covers at most one expected
  (``one_to_one``), since the skill reports one issue per offending element.
- ``decoy_checks``: elements a correct run leaves alone, by the rule exception
  that applies.
- ``title_checks``: this workflow's own deterministic checks (titles from the
  skill's four prefixes; a detected element issue names that element's label).
- ``judged_criteria``: two graded criteria on the suggested action, against
  the whole report (concrete about this element; grounded in the report).
- ``tool_called("view_image")``: on the samples whose document embeds an
  image, whether the agent looked at it.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --epochs 3
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
    expects_severities,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.scorers import tool_called
from evals_inspectai.e2e.figures_tables_check.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    title_scores,
)

WORKFLOW_TYPE = "figures_tables_check"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def title_checks() -> Scorer:
    """This workflow's own deterministic checks: known title prefixes, and the element's label in the title."""
    return deterministic_scorer(title_scores)


@task
def figures_tables_check_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Figures & Tables Check on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    severities = expects_severities(records)
    keys = issue_check_keys(edits=False, severities=severities)
    own = [
        *(("title_checks", key) for key in OWN_DESCRIPTIONS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
        ("tool_called", "tool_called"),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per offending element, matched on the rule its title names and "
                "anchored where the element sits; numbering issues are matched on 'Inconsistent Numbering' alone. "
                "Severity is expected where the issues skill fixes it (missing element high, unreferenced and "
                "numbering medium) and not checked for a missing title. Clean documents expect none; decoys are "
                "elements a correct run leaves alone. No edits are expected. A NaN metric value means the sample "
                "gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "title_checks": OWN_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
                "tool_called": {"tool_called": "On a sample whose document embeds an image, whether the agent called view_image."},
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=False, one_to_one=True, severities=severities),
            decoy_checks(reasons),
            title_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True),
            tool_called("view_image"),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            reasons,
            edits=False,
            extra=own,
            labels={**SCORE_LABELS, "tool_called": "Viewed image"},
            severities=severities,
        ),
    )
