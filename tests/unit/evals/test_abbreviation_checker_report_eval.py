"""The long-report Abbreviation Scan eval: the report, its definition-removed variants, and the task."""

from evals_inspectai.common.issue_inventory import decoy_reasons
from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import load_records
from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_report_e2e import (
    DATASET,
    abbreviation_checker_report_e2e,
)

UNDEFINED = "Abbreviation not defined at first use"


def test_report_dataset_is_well_formed():
    records = load_records(DATASET)
    assert len(records) == 10
    report, catalogue = records[0]
    assert len(report.document.split("\n")) == 818, "817 lines and a trailing newline"
    assert all(c.abbreviations_section_found for _, c in records)
    assert len(catalogue.abbreviations) == 273 and sum(not o.ignored for o in catalogue.abbreviations) == 128
    expected = [e for inventory, _ in records for e in inventory.expected_issues]
    assert all(e.severity == "medium" and e.anchor is not None for e in expected)
    assert all(e.required for e in expected)
    assert decoy_reasons([inventory for inventory, _ in records]) == (
        "always_excluded",
        "consistent_redefinition",
        "cover_page",
        "exempt_class",
        "first_definition",
        "later_occurrence",
        "references",
        "url",
    )
    assert all(inventory.notes for inventory, _ in records)


def test_each_variant_differs_from_the_report_only_by_its_removed_definitions():
    (report, report_catalogue), *variants = load_records(DATASET)
    report_lines = report.document.split("\n")
    report_ids = {e.id for e in report.expected_issues}
    for inventory, catalogue in variants:
        lines = inventory.document.split("\n")
        edited = {n for n, (a, b) in enumerate(zip(report_lines, lines), 1) if a != b}
        assert len(lines) == len(report_lines) and edited, inventory.notes
        assert len(catalogue.abbreviations) == len(report_catalogue.abbreviations), inventory.notes
        cleared = 0
        for before, after in zip(report_catalogue.abbreviations, catalogue.abbreviations):
            if before.inline_definition != after.inline_definition:
                assert before.line_start in edited and before.inline_definition and not after.inline_definition
                cleared += 1
            assert before.model_copy(update={"inline_definition": ""}) == after.model_copy(update={"inline_definition": ""})
        assert cleared >= len(edited), "every edited line removes at least one definition"
        added = [e for e in inventory.expected_issues if e.id not in report_ids]
        assert report_ids <= {e.id for e in inventory.expected_issues}
        assert all(e.title == UNDEFINED and e.line in edited for e in added), "a removal only adds Rule 2 where it edits"


def test_report_task_composition():
    t = abbreviation_checker_report_e2e()
    assert len(t.dataset) == 10 and len(t.scorer) == 3 and t.dataset.name == "abbreviation_checker_report"
    assert set(t.metadata["metrics"]) == {"catalogue_checks", "issue_checks", "decoy_checks"}
    assert "no_fp_url" in t.metadata["metrics"]["decoy_checks"]
