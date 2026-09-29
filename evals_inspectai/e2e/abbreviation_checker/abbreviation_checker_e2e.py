"""E2E eval for the Abbreviation Scan (v2) workflow: the extracted catalogue, and the issues a user sees.

Runs ``abbreviation_scan_v2`` through the API like every other e2e eval. The
workflow has two stages. First, extraction agents (one per chunk of the
document, ``skills/abbreviation-extraction/SKILL.md``) record every
abbreviation occurrence: its inline definition, occurrence number, lines, the
Abbreviations-section entry, and whether it is excluded. Then code
(``lib/workflows/abbreviation_scan_v2/issues.py::build_issues``) applies the
five rules of ``skills/abbreviation-scan/SKILL.md`` to that catalogue and
persists one issue per failure: "No Abbreviations section found",
"Abbreviation not defined at first use", "Abbreviation missing from
Abbreviations section", "Inline definition does not match Abbreviations
section" and "Ambiguous abbreviation", all medium. The solver fetches those
persisted issues from the app's project endpoint (``include_issues``), so the
issues are scored as the user sees them rather than only the intermediate
state.

Ground truth is ``dataset.yaml``. Each record has an expected catalogue and an
issue inventory. The inventory anchors each issue on the line of the offending
occurrence; the no-section issue is matched on its title alone. The records
cover: one-line exemption tests for each exempt class (titles, degrees, units,
citation elements, ranks, "U.S.", security markings, equipment designators,
all-caps corporations, genus abbreviations); headings, references and
footnotes; the always-excluded RAND, MIT and ChatGPT; plurals; a document with
no abbreviations at all; each rule failing on its own; an abbreviation used
bare before it is defined, which is Rule 2 at the bare use and sets Rule 5's
baseline at the first definition; and a long report catalogued in several
chunks.

Scorers:

- ``catalogue_checks``: the catalogue against the expected one, per occurrence
  keyed by (abbreviation, occurrence number). Occurrence recall and precision,
  then field accuracy over matched occurrences, plus the section flag and a
  clean catalogue on the document with no abbreviations (see ``criteria.py``).
- ``issue_checks``: the persisted issues against the inventory (recall,
  precision, F0.5, clean documents, title, severity, the anchor line inside
  the issue's range). One reported issue covers at most one expected
  (``one_to_one``), since the rules report one issue per abbreviation and rule.
- ``decoy_checks``: lines a correct run must not report under the given title,
  by reason (excluded occurrences, later uses, definitions that do not
  conflict).

The issue text comes from code, so nothing is judged by a model.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py --epochs 3
"""

from pathlib import Path
from typing import Any, Optional

from inspect_ai import Task, task
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from evals_inspectai.common.api_solver import PERSISTED_ISSUES_KEY, api_workflow_agent
from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.issue_checks import PER_KEY_METRICS
from evals_inspectai.common.issue_inventory import ResolvedInventory
from evals_inspectai.e2e.abbreviation_checker.criteria import (
    CATALOGUE_DESCRIPTIONS,
    CATALOGUE_KEYS,
    CATALOGUE_LABELS,
    ExpectedCatalogue,
    ReportedCatalogue,
    catalogue_scores,
)

WORKFLOW_TYPE = "abbreviation_scan_v2"
DATASET = Path(__file__).parent / "dataset.yaml"
# Record fields holding the expected catalogue, beside the inventory.
CATALOGUE_FIELDS = ("abbreviations_section_found", "abbreviations")
ISSUE_RESULTS = (PERSISTED_ISSUES_KEY,)
GROUND_TRUTH = (
    "Per record, the occurrence catalogue a correct extraction records (matched on abbreviation and "
    "occurrence number) and an inventory of the issues the workflow persists: the rule's exact title, "
    "severity medium, anchored on the line of the offending occurrence, except 'No Abbreviations section "
    "found', which is matched on its title alone. Decoys are lines a correct run leaves alone under the "
    "given title. No edits are expected. A NaN metric value means the sample gave that check nothing to judge."
)
OWN_METRICS = {"catalogue_checks": CATALOGUE_DESCRIPTIONS}

AbbreviationRecord = tuple[ResolvedInventory, ExpectedCatalogue]


def load_suite(path: Path = DATASET, name: Optional[str] = None) -> InventorySuite:
    """The records of ``path``: one issue per abbreviation and rule, so matching is one-to-one."""
    return InventorySuite.load(
        path, pairing="one_to_one", extra_fields=CATALOGUE_FIELDS, results=ISSUE_RESULTS, name=name
    )


def load_records(path: Path = DATASET) -> list[AbbreviationRecord]:
    """Each record's resolved inventory and expected catalogue."""
    suite = load_suite(path)
    return [(inventory, ExpectedCatalogue.model_validate(extra)) for inventory, extra in zip(suite.records, suite.extras)]


def _catalogue_metadata(extra: dict[str, Any]) -> dict[str, Any]:
    return {"catalogue": ExpectedCatalogue.model_validate(extra).model_dump()}


@scorer(metrics=PER_KEY_METRICS)
def catalogue_checks() -> Scorer:
    """The extracted occurrence catalogue against the expected one (see ``criteria.catalogue_scores``)."""

    async def score(state: TaskState, target: Target) -> Score:
        expected = ExpectedCatalogue.model_validate(state.metadata["catalogue"])
        try:
            reported = ReportedCatalogue.model_validate_json(state.output.completion)
        except ValidationError as e:
            return Score(value={key: 0.0 for key in CATALOGUE_KEYS}, explanation=f"could not parse the workflow state: {e}")
        values, explanation = catalogue_scores(reported, expected)
        return Score(value=values, explanation=explanation)

    return score


@task
def abbreviation_checker_e2e(timeout_s: float = 600) -> Task:
    """Run Abbreviation Scan on every sample and score its catalogue and its persisted issues.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
    """
    return build_task(load_suite(), timeout_s)


def build_task(suite: InventorySuite, timeout_s: float) -> Task:
    """The Abbreviation Scan task over ``suite``: the catalogue, issue and decoy scorers."""
    return Task(
        dataset=suite.dataset(_catalogue_metadata),
        metadata=suite.metadata(GROUND_TRUTH, OWN_METRICS),
        solver=api_workflow_agent(
            WORKFLOW_TYPE, timeout_s=timeout_s, item_messages_key="chunks", item_label="chunk", include_issues=True
        ),
        scorer=[catalogue_checks(), *suite.scorers()],
        fail_on_error=0.2,
        viewer=suite.viewer(OWN_METRICS, CATALOGUE_LABELS),
    )
