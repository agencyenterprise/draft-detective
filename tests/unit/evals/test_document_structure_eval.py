"""The Document Structure eval: its dataset, its task, and its own deterministic checks."""

import math
from pathlib import Path

from evals_inspectai.common.issue_inventory import (
    ResolvedInventory,
    expects_anchors,
    expects_edits,
    expects_severities,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.document_structure.criteria import (
    JUDGE_CRITERIA,
    TITLES,
    appendix_mentions,
    structure_scores,
)
from evals_inspectai.e2e.document_structure.document_structure_e2e import document_structure_e2e

DATASET = Path("evals_inspectai/e2e/document_structure/dataset.yaml")
DOC = (
    "# Report\n\n## Appendix A: Tables\n\n"
    "We compared renewal rates. Detailed regression tables are provided in the appendix. Nothing else.\n"
)
INVENTORY = ResolvedInventory(document=DOC, expected_issues=[], decoys=[])


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 19
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 13
    # Every issue is about a section the document lacks: matched on the title, no anchor.
    assert all(e.anchor is None and e.title in TITLES for e in expected)
    assert {e.title for e in expected} == set(TITLES), "every section, the appendix included, is missing somewhere"
    assert all(e.severity == "high" for e in expected)
    assert sum(1 for r in records if not r.expected_issues) == 10
    assert expects_anchors(records) is False and expects_severities(records) is True
    assert expects_edits(records) is False
    assert all(r.notes for r in records), "every record says why it exists"


def test_task_emits_only_the_keys_an_unanchored_inventory_can_score():
    t = document_structure_e2e()
    assert len(t.scorer) == 3 and len(t.dataset) == 19
    assert list(t.metadata["metrics"]["issue_checks"]) == ["recall", "precision", "f0_5", "clean_document_untouched", "severity_correct"]
    assert set(t.metadata["metrics"]) == {"issue_checks", "structure_checks", "judged_criteria"}
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__issue_checks__anchor_in_range" not in columns
    assert "score__structure_checks__known_titles" in columns and "score__judged_criteria__action_specific" in columns


def test_judged_criteria_read_the_suggested_action_against_the_whole_report():
    assert {c.key for c in JUDGE_CRITERIA} == {"action_specific", "action_grounded"}
    assert all(c.scope == "expected" and c.passage == "document" and c.applies_to is None for c in JUDGE_CRITERIA)


def test_appendix_mentions_skip_headings_and_split_sentences():
    assert appendix_mentions(DOC) == [(5, "Detailed regression tables are provided in the appendix.")]


def test_titles_outside_the_skills_set_are_counted():
    issues = [IssueItem(title="Missing Section: Methods"), IssueItem(title="Missing Methodology Section")]
    values, note = structure_scores(issues, INVENTORY)
    assert values["known_titles"] == 0.5
    assert "Missing Methodology Section" in note


def test_an_appendix_issue_must_point_to_the_sentence_that_refers_to_it():
    quoted = IssueItem(title="Missing Section: Appendix", description="The body says “regression tables are provided in the appendix” but there is none.", start_line=1, end_line=1)
    by_line = IssueItem(title="Missing Section: Appendix", description="The appendix referred to on line 5 is missing.", start_line=1, end_line=1)
    placed = IssueItem(title="Missing Section: Appendix", description="An appendix is referenced but missing.", start_line=5, end_line=5)
    vague = IssueItem(title="Missing Section: Appendix", description="An appendix is referenced but missing.", start_line=1, end_line=1)
    values, _ = structure_scores([quoted, by_line, placed], INVENTORY)
    assert values["appendix_reference_cited"] == 1.0
    values, note = structure_scores([quoted, vague], INVENTORY)
    assert values["appendix_reference_cited"] == 0.5 and "1/2 appendix issues" in note


def test_structure_checks_are_nan_with_nothing_to_judge():
    values, _ = structure_scores([], INVENTORY)
    assert math.isnan(values["known_titles"]) and math.isnan(values["appendix_reference_cited"])
    values, _ = structure_scores([IssueItem(title="Missing Section: Methods")], INVENTORY)
    assert values["known_titles"] == 1.0 and math.isnan(values["appendix_reference_cited"])
