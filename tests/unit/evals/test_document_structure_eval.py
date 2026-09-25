"""The Document Structure eval's dataset and task, without a model."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import expects_anchors, expects_severities, load_inventory_records
from evals_inspectai.e2e.document_structure.document_structure_e2e import document_structure_e2e

DATASET = Path("evals_inspectai/e2e/document_structure/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 5
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 7
    # Every issue is about a section the document lacks: matched on the title, no anchor.
    assert all(e.anchor is None and e.title is not None and e.title.startswith("Missing Section: ") for e in expected)
    assert expects_anchors(records) is False and expects_severities(records) is False
    assert sum(1 for r in records if not r.expected_issues) == 1


def test_task_emits_only_the_keys_an_unanchored_inventory_can_score():
    t = document_structure_e2e()
    assert len(t.scorer) == 2 and len(t.dataset) == 5
    assert list(t.metadata["metrics"]["issue_checks"]) == ["recall", "precision", "f0_5", "clean_document_untouched"]
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__issue_checks__anchor_in_range" not in columns and "score__issue_checks__severity_correct" not in columns
