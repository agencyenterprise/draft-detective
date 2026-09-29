"""E2E eval for the Document Structure (Document Contents) workflow, on the issue-inventory structure.

Declared by ``skills/document-contents/SKILL.md``; runs through the API like
every other e2e eval. The workflow reports one "Missing Section: <name>" issue
per required section the document lacks, and one for an appendix the body
refers to but the document does not contain. Every such issue is about
something absent, so no expected issue has an anchor: each is matched on its
title alone, and the line-range check is not emitted.

Ground truth is ``dataset.yaml``: documents that present each section under
its main heading, under the alternatives the skill lists, under deep headings
or as bold-labelled blocks; documents missing one section at a time, including
traps where the section's name appears without the section (a mention of
methods in the introduction, a "Methods of Payment" section about the report's
subject, "results are expected" in an interim report); every branch of the
conditional appendix (referenced and present, present but never referenced,
referenced in lowercase and missing, present under "Supplementary Material",
mentioned only in a cited work's title); and two published reports whose
findings sit under a Summary or finding-titled chapters rather than a Results
heading.

Scorers: the reusable ``issue_checks`` (severity included: a missing required
section is high), this workflow's own deterministic checks (titles from the
skill's set; an appendix issue quotes the sentence referring to it), and two
judged criteria on the suggested actions, graded against the whole report.
Each finding is one issue, so matching is ``one_to_one``.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/document_structure/document_structure_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.issue_checks import PER_KEY_METRICS, deterministic_scorer
from evals_inspectai.e2e.document_structure.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    structure_scores,
)

WORKFLOW_TYPE = "document_structure"
DATASET = Path(__file__).parent / "dataset.yaml"
GROUND_TRUTH = (
    "Inventory: one expected issue per missing section, matched on its 'Missing Section: <name>' title "
    "(no anchor, since the section is absent) with severity high; clean documents expect none. No edits "
    "are expected. A NaN metric value means the sample gave that check nothing to judge."
)
OWN_METRICS = {"structure_checks": OWN_DESCRIPTIONS, "judged_criteria": JUDGE_DESCRIPTIONS}


@scorer(metrics=PER_KEY_METRICS)
def structure_checks() -> Scorer:
    """This workflow's own deterministic checks: known titles, and appendix issues citing the reference."""
    return deterministic_scorer(structure_scores)


@task
def document_structure_e2e(timeout_s: float = 300, judge_calls: int = 1) -> Task:
    """Run Document Structure on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    suite = InventorySuite.load(DATASET, pairing="one_to_one")
    return Task(
        dataset=suite.dataset(),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[*suite.scorers(), structure_checks(), suite.judged(JUDGE_CRITERIA, calls=judge_calls)],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, SCORE_LABELS),
    )
