"""The Live Reports eval: its dataset and its task."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import load_inventory_records
from evals_inspectai.e2e.live_reports_v2.live_reports_v2_e2e import live_reports_v2_e2e

DATASET = Path("evals_inspectai/e2e/live_reports_v2/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 12
    assert all(r.publication_date for r in records), "every live report is dated"
    required = [e for r in records for e in r.expected_issues if e.required]
    assert len(required) == 18 and all(e.anchor and e.rationale for e in required)
    assert sum(1 for r in records if not r.expected_issues) == 2
    for record in records:
        claimed = {e.line for e in record.expected_issues}
        lines = record.document.split("\n")
        for decoy in record.decoys:
            assert next(n for n, line in enumerate(lines, 1) if decoy.anchor in line) not in claimed, decoy.anchor


def test_task_checks_sources_are_new_and_after_the_publication_date():
    t = live_reports_v2_e2e()
    assert len(t.dataset) == 12 and len(t.scorer) == 4
    assert all(s.metadata["publication_date"] for s in t.dataset)
    assert "not_already_cited" in t.metadata["metrics"]["source_checks"]
