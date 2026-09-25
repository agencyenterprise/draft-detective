"""E2E eval for the About This (GER) workflow, on the issue-inventory structure.

Declared by ``skills/about-this-preface/SKILL.md`` and
``skills/about-this-authors/SKILL.md``; runs through the API like every other
e2e eval. The workflow runs the two validators in parallel and keeps each one's
issues in its own state field (``preface_result``, ``authors_result``); every
scorer here reads both together (``RESULTS``), since the titles already say
which validator an issue came from. Each validator's conversation is captured
as a transcript (``agent_conversations``).

Ground truth is ``dataset.yaml``: a seed report passing every rule and twelve
ablations of it that each break one rule (each preface element, each bio rule,
each missing section), plus reports of their own for what the seed cannot
reach: two preface elements missing at once; one author failing two rules;
three and four authors, one failing; a single author under "About the Author";
the alternative headings the skills list (Preface, Introduction, Executive
Summary, About This Publication, Author Biographies, Contributors, The
Authors); bios whose abbreviations (Ph.D., M.A., Dr., e.g., i.e.) must not end
a sentence; M.P.P. and J.D. as the highest degree; a paragraph under 50
characters that is no bio; a position without an affiliation; a "Dr." with no
degree named; a missing author section alongside a preface failure; and
compliant reports on other topics. Decoys mark the bios a correct run leaves
alone for those reasons.

A failed preface element or a missing section is about something absent, so
its expected issue has no anchor and is matched on its title; an author issue
is anchored on the bio and matched on the stable "Author Bio Issue" part of its
title. Each finding is its own issue, so matching is ``one_to_one``. Where one
author fails two rules, the skill lets the run report one issue per rule or one
issue listing both: the first rule's issue is required and the second optional,
so a split run matches both and a combined one matches the required one without
losing precision or recall (neither can then tell a combined issue from one
naming only one failure; the judge reads what the action names).

Scorers: the reusable ``issue_checks`` and ``decoy_checks`` (severity included:
every issue is medium), this workflow's own deterministic checks (titles from
the skills' sets, medium severity on every reported issue, a "section not
found" issue alone in its validator, author titles naming the bio's author),
and two judged criteria on the suggested actions (see ``criteria.py``).

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/about_this_ger/about_this_ger_e2e.py --epochs 3
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
    expects_anchors,
    expects_severities,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.e2e.about_this_ger.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    about_scores,
)

WORKFLOW_TYPE = "about_this_ger"
DATASET = Path(__file__).parent / "dataset.yaml"
# The state fields holding each validator's AgentCheckResult.
RESULTS = ("preface_result", "authors_result")


@scorer(metrics=PER_KEY_METRICS)
def about_checks() -> Scorer:
    """This workflow's own deterministic checks: known titles, medium severity,
    "not found" issues alone, author titles naming the bio's author."""
    return deterministic_scorer(about_scores, RESULTS)


@task
def about_this_ger_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run About This (GER) on every sample and score both validators against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    anchors, severities = expects_anchors(records), expects_severities(records)
    keys = issue_check_keys(edits=False, anchors=anchors, severities=severities)
    own = [
        *(("about_checks", key) for key in OWN_DESCRIPTIONS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per broken rule across both validators, severity medium. Preface "
                "elements and missing sections are matched on their title (no anchor, since the content is absent); "
                "author issues are anchored on the bio. Where one author fails two rules, the second is optional, "
                "since the skill allows one combined issue. Decoys mark bios a correct run leaves alone. No edits "
                "are expected. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "about_checks": OWN_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s, item_messages_key="agent_conversations"),
        scorer=[
            issue_checks(edits=False, one_to_one=True, anchors=anchors, severities=severities, results=RESULTS),
            decoy_checks(reasons, results=RESULTS),
            about_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True, results=RESULTS),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            reasons, edits=False, extra=own, labels=SCORE_LABELS, anchors=anchors, severities=severities
        ),
    )
