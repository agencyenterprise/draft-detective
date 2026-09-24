"""The Recommendation Check eval's dataset and task, without a model."""

from collections import Counter
from pathlib import Path

from evals_inspectai.common.issue_inventory import decoy_reasons, expects_edits, expects_titles, load_inventory_records
from evals_inspectai.e2e.recommendation_check.criteria import AUDIENCE_TITLE, NOT_ACTIONABLE_TITLE, TOO_MANY_TITLE
from evals_inspectai.e2e.recommendation_check.recommendation_check_e2e import recommendation_check_e2e

DATASET = Path("evals_inspectai/e2e/recommendation_check/dataset.yaml")
NEW_KINDS = {NOT_ACTIONABLE_TITLE: "medium", AUDIENCE_TITLE: "medium", TOO_MANY_TITLE: "low"}


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 15
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 49
    # Support issues have free-form titles; the classification is the severity, left
    # unset where two classifications are defensible.
    support = [e for e in expected if e.title is None]
    assert all(e.severity in {"none", "medium", "high", None} for e in support)
    assert Counter(e.severity for e in support) == {"none": 13, "medium": 12, "high": 7, None: 6}
    # The EEI item 8 kinds carry their fixed title and severity.
    kinds = [e for e in expected if e.title is not None]
    assert all(NEW_KINDS[e.title] == e.severity for e in kinds)
    assert Counter(e.title for e in kinds) == {NOT_ACTIONABLE_TITLE: 5, AUDIENCE_TITLE: 5, TOO_MANY_TITLE: 1}
    assert [e.id for e in expected if not e.required] == ["near_miss_not_actionable", "contractor_sites_audience"]
    # Every recommendation a new-kind issue sits on also has its support issue.
    for r in records:
        support_anchors = {e.anchor for e in r.expected_issues if e.title is None}
        assert all(e.anchor in support_anchors for e in r.expected_issues if e.title in (NOT_ACTIONABLE_TITLE, AUDIENCE_TITLE))
    assert sum(1 for r in records if not r.expected_issues) == 1
    # The pairing reads the fixed-title kinds off the whole dataset, so a record with no
    # expected issue of a kind still ranks a report of it below a free-form support issue.
    assert all(r.named_titles == sorted(NEW_KINDS) for r in records)
    # A decoy on a recommendation must name the kind it guards against, or the support
    # issue every recommendation gets would flag it.
    assert all(d.title in NEW_KINDS for r in records for d in r.decoys if d.reason != "conclusion")
    assert decoy_reasons(records) == (
        "conclusion",
        "concrete_action",
        "heading_audience",
        "hedged_concrete",
        "lead_in_audience",
        "restatements_counted_once",
        "single_actor",
        "sub_items",
        "three_or_fewer",
        "unquantified_action",
    )
    assert expects_edits(records) is False, "nothing in the inventory mentions edits, so the edit checks are off"
    assert expects_titles(records) is True, "the new kinds name their titles, so title_correct is scored"


def test_task_composes_the_inventory_scorers_the_image_check_and_the_judge():
    t = recommendation_check_e2e()
    assert len(t.scorer) == 4
    assert len(t.dataset) == 15
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "tool_called", "judged_criteria"}
    assert set(t.metadata["metrics"]["judged_criteria"]) == {"action_concrete", "audience_asked", "pare_down_named"}
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__issue_checks__recall" in columns and "score__tool_called__tool_called" in columns
    assert "score__judged_criteria__audience_asked" in columns
    assert not any("edit_" in c for c in columns), "a workflow with no edits has no edit columns"
    assert "score__issue_checks__title_correct" in columns
    assert "title_correct" in t.metadata["metrics"]["issue_checks"]
