"""E2E eval for the Structural Checks (GER) workflow, on the issue-inventory structure.

The workflow is declared by its skill (``skills/structural-checks-ger/SKILL.md``)
and runs through the API like every other e2e eval. It combines the rules of the
About This (GER) and Document Contents checks, which it replaces in the picker,
and this suite combines their samples: each one completed so that the parts it
does not test pass (see the header of ``dataset.yaml``).

Ground truth is ``dataset.yaml`` in inventory form. A missing section and a
missing preface element are about something absent, so their expected issues
have no anchor and are matched on their titles; an author issue is anchored on
the bio, and an appendix issue on the sentence that refers to the appendix,
where the skill places them. The samples cover every required section missing
on its own, the alternative headings the skill lists, deep headings and
bold-labelled blocks, traps where a section's name appears without the section,
every branch of the conditional appendix, each preface element failing, every
bio rule failing, one author failing two rules, one to four authors, sentence
counting around abbreviations, professional degrees, short non-bio lines, a
missing preface or author section alongside other failures, and two published
reports. Decoys mark the bios a correct run leaves alone. Each finding is its
own issue, so matching is ``one_to_one``.

Scorers: the reusable ``issue_checks`` and ``decoy_checks``, which hold titles,
severities (high for a missing section, medium otherwise) and placement to the
inventory, and four judged criteria on the suggested actions. The criteria take
their rules from the skill file rather than restating them (``criteria.py``),
so the suite keeps no copy of the rules of its own.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/structural_checks_ger/structural_checks_ger_e2e.py --epochs 3
    uv run inspect eval evals_inspectai/e2e/structural_checks_ger/structural_checks_ger_e2e.py --sample-id=2
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.e2e.structural_checks_ger.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    SCORE_LABELS,
)

WORKFLOW_TYPE = "structural_checks_ger"
DATASET = Path(__file__).parent / "dataset.yaml"
GROUND_TRUTH = (
    "Inventory: one expected issue per missing section (severity high), per missing preface element and per "
    "author whose bio fails a rule (both medium). Missing sections and preface elements are matched on their "
    "title (no anchor, since the content is absent); author issues are anchored on the bio and appendix issues on "
    "the sentence that refers to the appendix. On the published "
    "reports, preface elements a careful reader could judge either way are optional. Decoys mark bios a correct "
    "run leaves alone. No edits are expected. A NaN metric value means the sample gave that check nothing to "
    "judge."
)
OWN_METRICS = {"judged_criteria": JUDGE_DESCRIPTIONS}


@task
def structural_checks_ger_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Structural Checks (GER) on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    suite = InventorySuite.load(DATASET, pairing="one_to_one")
    return Task(
        dataset=suite.dataset(),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            *suite.scorers(),
            suite.judged(JUDGE_CRITERIA, calls=judge_calls),
        ],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, SCORE_LABELS),
    )
