"""The Recommendation Check eval's dataset and task, without a model."""

from collections import Counter
from pathlib import Path

from evals_inspectai.common.issue_inventory import decoy_reasons, expects_edits, expects_titles, load_inventory_records
from evals_inspectai.e2e.recommendation_check.recommendation_check_e2e import recommendation_check_e2e

DATASET = Path("evals_inspectai/e2e/recommendation_check/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 8
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 18
    # Titles are free-form for this workflow; the classification is the severity.
    assert all(e.title is None and e.severity in {"none", "medium", "high"} for e in expected)
    assert Counter(e.severity for e in expected) == {"none": 4, "medium": 7, "high": 7}
    assert sum(1 for r in records if not r.expected_issues) == 1
    assert decoy_reasons(records) == ("conclusion",)
    assert expects_edits(records) is False, "nothing in the inventory mentions edits, so the edit checks are off"
    assert expects_titles(records) is False, "no titles named, so title_correct is not emitted"


def test_task_composes_the_inventory_scorers_and_the_image_check():
    t = recommendation_check_e2e()
    assert len(t.scorer) == 3
    assert len(t.dataset) == 8
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "tool_called"}
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__issue_checks__recall" in columns and "score__tool_called__tool_called" in columns
    assert not any("edit_" in c for c in columns), "a workflow with no edits has no edit columns"
    assert "score__issue_checks__title_correct" not in columns, "free-form titles: no Title column"
    assert "title_correct" not in t.metadata["metrics"]["issue_checks"]
