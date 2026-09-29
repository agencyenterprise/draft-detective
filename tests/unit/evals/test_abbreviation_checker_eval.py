"""The Abbreviation Scan eval: its dataset, its task, and the catalogue scorer."""

import json
import math
import re
from pathlib import Path
from typing import Any, Optional

import pytest
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Target
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from evals_inspectai.common.api_solver import PERSISTED_ISSUES_KEY
from evals_inspectai.common.issue_inventory import ResolvedInventory, decoy_reasons, expects_edits, normalize
from evals_inspectai.e2e.abbreviation_checker import abbreviation_checker_report_e2e
from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import (
    DATASET,
    abbreviation_checker_e2e,
    catalogue_checks,
    load_suite,
)
from evals_inspectai.e2e.abbreviation_checker.criteria import (
    CATALOGUE_KEYS,
    ExpectedCatalogue,
    ExpectedOccurrence,
    ReportedCatalogue,
    ReportedOccurrence,
    catalogue_scores,
)


def load_records(path: Path = DATASET) -> list[tuple[ResolvedInventory, ExpectedCatalogue]]:
    """Each record's inventory with its expected catalogue."""
    suite = load_suite(path)
    return [(inventory, ExpectedCatalogue.model_validate(extra)) for inventory, extra in zip(suite.records, suite.extras)]

NO_SECTION = "No Abbreviations section found"
TITLES = {
    NO_SECTION,
    "Abbreviation not defined at first use",
    "Abbreviation missing from Abbreviations section",
    "Inline definition does not match Abbreviations section",
    "Ambiguous abbreviation",
}


def _appears_on(abbr: str, text: str) -> bool:
    """The abbreviation as a whole token, allowing a plural "s" (the skill records the singular)."""
    return re.search(r"(?<![A-Za-z])" + re.escape(abbr) + r"s?(?![A-Za-z])", text) is not None


def test_dataset_is_well_formed():
    records = load_records()
    assert len(records) == 36
    inventories = [inventory for inventory, _ in records]
    expected = [e for inventory in inventories for e in inventory.expected_issues]
    assert len(expected) == 22
    assert sum(1 for inventory in inventories if not inventory.expected_issues) == 24
    assert {e.title for e in expected} == TITLES, "every rule fails somewhere"
    assert all(e.severity == "medium" for e in expected)
    # Only the no-section issue is about something absent; every other issue sits on its occurrence's line.
    assert all((e.anchor is None) == (e.title == NO_SECTION) for e in expected)
    assert expects_edits(inventories) is False
    assert decoy_reasons(inventories) == (
        "always_excluded",
        "consistent_redefinition",
        "exempt_class",
        "first_definition",
        "footnote",
        "heading",
        "later_occurrence",
        "references",
    )
    assert all(inventory.notes for inventory in inventories), "every record says why it exists"
    assert all(inventory.target_answer is None for inventory in inventories), "the model-graded target was dropped"
    assert sum(1 for _, catalogue in records if not catalogue.abbreviations) == 1, "one document has no abbreviations"
    assert max(len(inventory.document) for inventory in inventories) > 8_000, "one document spans several chunks"


BOTH_DATASETS = pytest.mark.parametrize("dataset", [DATASET, abbreviation_checker_report_e2e.DATASET], ids=["short", "report"])


@BOTH_DATASETS
def test_every_catalogue_occurrence_is_on_its_lines(dataset):
    for inventory, catalogue in load_records(dataset):
        lines = inventory.document.split("\n")
        for o in catalogue.abbreviations:
            assert o.line_end is not None and o.line_end <= len(lines)
            assert _appears_on(o.abbr, " ".join(lines[o.line_start - 1 : o.line_end])), f"{o.abbr} not on line {o.line_start}"
            assert not o.inline_definition or normalize(o.inline_definition) in normalize(lines[o.line_start - 1])
        # The expected issues agree with the catalogue on where each rule fires.
        found = catalogue.abbreviations_section_found
        assert any(e.title == NO_SECTION for e in inventory.expected_issues) == (
            not found and any(not o.ignored for o in catalogue.abbreviations)
        )
        if not found:
            assert all(o.abbreviations_section_definition is None for o in catalogue.abbreviations)


@BOTH_DATASETS
def test_every_anchored_issue_sits_on_an_occurrence_line(dataset):
    for inventory, catalogue in load_records(dataset):
        in_scope_lines = {o.line_start for o in catalogue.abbreviations if not o.ignored}
        for e in inventory.expected_issues:
            assert e.anchor is None or e.line in in_scope_lines, f"{e.id} is not on a non-excluded occurrence"


def test_catalogue_occurrences_must_be_numbered_in_line_order():
    with pytest.raises(ValidationError, match="do not run 1..n"):
        ExpectedCatalogue.model_validate(
            {"abbreviations_section_found": False, "abbreviations": [{"abbr": "AI", "occurrence_number": 2, "line_start": 1}]}
        )
    with pytest.raises(ValidationError):
        ExpectedOccurrence.model_validate({"abbr": "AI", "occurrence_number": 1, "line_start": 1, "reason": "x"})


def test_task_composition():
    t = abbreviation_checker_e2e()
    assert len(t.dataset) == 36 and len(t.scorer) == 3
    assert set(t.metadata["metrics"]) == {"catalogue_checks", "issue_checks", "decoy_checks"}
    assert list(t.metadata["metrics"]["catalogue_checks"]) == list(CATALOGUE_KEYS)
    assert list(t.metadata["metrics"]["issue_checks"]) == [
        "recall", "precision", "f0_5", "clean_document_untouched", "title_correct", "severity_correct", "anchor_in_range",
    ]
    sample = t.dataset[0]
    assert sample.metadata is not None and {"inventory", "catalogue"} <= set(sample.metadata)
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__catalogue_checks__occurrence_recall" in columns and "score__decoy_checks__no_fp_heading" in columns
    assert not any("edit_" in c for c in columns)


EXPECTED = ExpectedCatalogue(
    abbreviations_section_found=True,
    abbreviations=[
        ExpectedOccurrence(abbr="AI", occurrence_number=1, line_start=5, inline_definition="Artificial Intelligence", abbreviations_section_definition="Artificial Intelligence"),
        ExpectedOccurrence(abbr="AI", occurrence_number=2, line_start=7, abbreviations_section_definition="Artificial Intelligence"),
        ExpectedOccurrence(abbr="U.S.", occurrence_number=1, line_start=7, ignored=True),
    ],
)


def _reported(changes: Optional[dict[str, dict[str, Any]]] = None) -> ReportedCatalogue:
    """The expected catalogue as a correct run reports it, with per-occurrence field changes keyed "abbr#n"."""
    occurrences = []
    for e in EXPECTED.abbreviations:
        fields = {**e.model_dump(), **(changes or {}).get(f"{e.abbr}#{e.occurrence_number}", {})}
        occurrences.append(ReportedOccurrence(**fields))
    return ReportedCatalogue(abbreviations=occurrences, abbreviations_section_found=True)


def test_a_correct_catalogue_scores_one_everywhere_it_applies():
    values, _ = catalogue_scores(_reported(), EXPECTED)
    assert math.isnan(values.pop("clean_catalogue"))
    assert all(v == 1.0 for v in values.values())


def test_a_missing_occurrence_costs_recall_only():
    reported = _reported()
    reported.abbreviations.pop(1)
    values, note = catalogue_scores(reported, EXPECTED)
    assert values["occurrence_recall"] == pytest.approx(2 / 3) and values["occurrence_precision"] == 1.0
    assert values["lines_correct"] == 1.0 and "missing 1: AI#2 (line 7)" in note


def test_a_missed_use_does_not_cost_the_later_uses_whose_numbers_it_shifts():
    expected = ExpectedCatalogue(
        abbreviations_section_found=False,
        abbreviations=[ExpectedOccurrence(abbr="AI", occurrence_number=n, line_start=line, ignored=line == 9) for n, line in ((1, 5), (2, 7), (3, 9), (4, 11))],
    )
    # The workflow numbers the recorded uses, so without the use on line 7 the later ones come back as #2 and #3.
    reported = ReportedCatalogue(
        abbreviations=[
            ReportedOccurrence(abbr="AI", occurrence_number=n, line_start=line, line_end=line, ignored=line == 9)
            for n, line in ((1, 5), (2, 9), (3, 11))
        ]
    )
    values, note = catalogue_scores(reported, expected)
    assert values["occurrence_recall"] == 0.75 and values["occurrence_precision"] == 1.0
    assert values["lines_correct"] == values["ignored_correct"] == 1.0
    assert "missing 1: AI#2 (line 7)" in note


def test_an_invented_occurrence_costs_precision_only():
    reported = _reported()
    reported.abbreviations.append(ReportedOccurrence(abbr="IT", occurrence_number=1, line_start=7, line_end=7))
    values, note = catalogue_scores(reported, EXPECTED)
    assert values["occurrence_recall"] == 1.0 and values["occurrence_precision"] == 0.75
    assert "invented 1: IT#1" in note


def test_a_wrong_line_costs_lines_correct_only():
    values, note = catalogue_scores(_reported({"AI#2": {"line_start": 8, "line_end": 8}}), EXPECTED)
    assert values["lines_correct"] == pytest.approx(2 / 3)
    assert values["occurrence_recall"] == values["occurrence_precision"] == values["inline_definition_correct"] == 1.0
    assert "AI#2 lines 8-8, expected 7-7" in note


def test_definitions_are_compared_without_case_or_spacing():
    values, _ = catalogue_scores(_reported({"AI#1": {"inline_definition": " artificial  intelligence "}}), EXPECTED)
    assert values["inline_definition_correct"] == 1.0
    values, _ = catalogue_scores(_reported({"AI#1": {"inline_definition": ""}, "U.S.#1": {"ignored": False}}), EXPECTED)
    assert values["inline_definition_correct"] == pytest.approx(2 / 3) and values["ignored_correct"] == pytest.approx(2 / 3)
    values, _ = catalogue_scores(_reported({"AI#2": {"abbreviations_section_definition": None}}), EXPECTED)
    assert values["section_definition_correct"] == pytest.approx(2 / 3)


def test_a_clean_document_scores_only_the_clean_catalogue():
    clean = ExpectedCatalogue(abbreviations_section_found=False, abbreviations=[])
    values, _ = catalogue_scores(ReportedCatalogue(), clean)
    assert values["clean_catalogue"] == 1.0 and values["section_found_correct"] == 1.0
    assert all(math.isnan(values[k]) for k in CATALOGUE_KEYS if k not in ("clean_catalogue", "section_found_correct"))
    invented = ReportedCatalogue(abbreviations=[ReportedOccurrence(abbr="IT", occurrence_number=1, line_start=3, line_end=3)])
    values, note = catalogue_scores(invented, clean)
    assert values["clean_catalogue"] == 0.0 and "IT#1" in note


def _state(completion: str) -> TaskState:
    inventory, catalogue = load_records()[0]
    state = TaskState(
        model="api",  # type: ignore[arg-type]  # TaskState coerces a model name
        sample_id=1,
        epoch=1,
        input=inventory.document,
        messages=[],
        metadata={"inventory": inventory.model_dump(), "catalogue": catalogue.model_dump()},
    )
    state.output = ModelOutput(completion=completion, model="api")
    return state


@pytest.mark.asyncio
async def test_the_scorer_reads_the_catalogue_from_the_workflow_state():
    _, catalogue = load_records()[0]
    completion = json.dumps(
        {
            "abbreviations": [o.model_dump() for o in catalogue.abbreviations],
            "abbreviations_section_found": True,
            PERSISTED_ISSUES_KEY: {"issues": []},
            "chunks": [],
        }
    )
    score = await catalogue_checks()(_state(completion), Target(""))
    assert isinstance(score.value, dict) and score.value["occurrence_recall"] == 1.0
    broken = await catalogue_checks()(_state("not json"), Target(""))
    assert isinstance(broken.value, dict) and set(broken.value.values()) == {0.0}
