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

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from evals_inspectai.common.api_solver import PERSISTED_ISSUES_KEY, api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    PER_KEY_METRICS,
    decoy_checks,
    decoy_descriptions,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import (
    InventoryRecord,
    ResolvedInventory,
    decoy_reasons,
    expects_severities,
    inventory_to_sample,
    resolve_record,
)
from evals_inspectai.common.issue_viewer import issue_viewer_config
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
# Record fields holding the expected catalogue. They are taken out before the rest is validated as an
# InventoryRecord, which forbids unknown fields.
CATALOGUE_FIELDS = ("abbreviations_section_found", "abbreviations")
ISSUE_RESULTS = (PERSISTED_ISSUES_KEY,)

AbbreviationRecord = tuple[ResolvedInventory, ExpectedCatalogue]


def load_records(path: Path = DATASET) -> list[AbbreviationRecord]:
    """Each record's resolved inventory and expected catalogue, with the inventory's ``named_titles`` set
    across the dataset as ``load_inventory_records`` sets it."""
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a YAML list of records")
    loaded: list[AbbreviationRecord] = []
    for record in raw:
        catalogue = ExpectedCatalogue.model_validate({k: record.pop(k) for k in CATALOGUE_FIELDS if k in record})
        loaded.append((resolve_record(InventoryRecord.model_validate(record)), catalogue))
    named = sorted({e.title for inventory, _ in loaded for e in inventory.expected_issues if e.title})
    return [(inventory.model_copy(update={"named_titles": named}), catalogue) for inventory, catalogue in loaded]


def to_sample(inventory: ResolvedInventory, catalogue: ExpectedCatalogue) -> Sample:
    sample = inventory_to_sample(inventory)
    sample.metadata = {**(sample.metadata or {}), "catalogue": catalogue.model_dump()}
    return sample


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
    return build_task(load_records(), DATASET, DATASET.parent.name, timeout_s)


def build_task(records: list[AbbreviationRecord], dataset: Path, name: str, timeout_s: float) -> Task:
    """The Abbreviation Scan task over ``records``, loaded from ``dataset``: the catalogue, issue and decoy scorers."""
    inventories = [inventory for inventory, _ in records]
    reasons = list(decoy_reasons(inventories))
    severities = expects_severities(inventories)
    keys = issue_check_keys(edits=False, severities=severities)
    return Task(
        dataset=MemoryDataset(samples=[to_sample(*r) for r in records], name=name, location=str(dataset)),
        metadata={
            "ground_truth": (
                "Per record, the occurrence catalogue a correct extraction records (matched on abbreviation and "
                "occurrence number) and an inventory of the issues the workflow persists: the rule's exact title, "
                "severity medium, anchored on the line of the offending occurrence, except 'No Abbreviations section "
                "found', which is matched on its title alone. Decoys are lines a correct run leaves alone under the "
                "given title. No edits are expected. A NaN metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "catalogue_checks": CATALOGUE_DESCRIPTIONS,
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
            },
        },
        solver=api_workflow_agent(
            WORKFLOW_TYPE, timeout_s=timeout_s, item_messages_key="chunks", item_label="chunk", include_issues=True
        ),
        scorer=[
            catalogue_checks(),
            issue_checks(edits=False, one_to_one=True, severities=severities, results=ISSUE_RESULTS),
            decoy_checks(reasons, results=ISSUE_RESULTS),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(
            reasons,
            edits=False,
            extra=[("catalogue_checks", key) for key in CATALOGUE_KEYS],
            labels=CATALOGUE_LABELS,
            severities=severities,
        ),
    )
