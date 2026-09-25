"""The Advocacy & Tone v2 eval: its dataset, its task, and its own deterministic checks."""

import math
from collections import Counter
from pathlib import Path

from evals_inspectai.common.issue_checks import issue_detection_scores
from evals_inspectai.common.issue_inventory import (
    ResolvedInventory,
    decoy_reasons,
    expects_edits,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.advocacy_tone_v2.advocacy_tone_v2_e2e import advocacy_tone_v2_e2e
from evals_inspectai.e2e.advocacy_tone_v2.criteria import (
    JUDGE_CRITERIA,
    SEVERITY_BY_TITLE,
    skipped_lines,
    tone_scores,
)

DATASET = Path("evals_inspectai/e2e/advocacy_tone_v2/dataset.yaml")
DOC = "\n".join(
    [
        "# Report",  # 1
        "",
        "## Findings",  # 3
        "The results clearly show a gain.",  # 4
        "",
        "## About the Authors",  # 6
        "She is undoubtedly brilliant.",  # 7
        "",
        "## Appendix A",  # 9
        "### A.1 Protocol",  # 10
        "Coders must always log the date.",  # 11
        "## Discussion",  # 12
        "We believe more study is needed.",  # 13
    ]
)
INVENTORY = ResolvedInventory(document=DOC, expected_issues=[], decoys=[])
LISTED_WORDS = (
    "obviously", "clearly", "undoubtedly", "certainly", "definitely", "absolutely", "always", "never",
    "we believe", "in our opinion", "it is clear that", "without doubt", "everyone knows",
    "urgent", "requires", "must", "critical", "essential", "ensure", "ensuring",
)


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 26
    required = [e for r in records for e in r.expected_issues if e.required]
    assert Counter(e.title for e in required) == {
        "Advocacy Language Detected": 16,
        "Trigger Words Detected": 8,
        "Subjective Tone Detected": 5,
    }
    assert sum(1 for r in records for e in r.expected_issues if not e.required) == 7
    assert all(e.severity == SEVERITY_BY_TITLE[e.title] for r in records for e in r.expected_issues if e.title)
    assert sum(1 for r in records if not r.expected_issues) == 9
    assert sum(1 for r in records if len([e for e in r.expected_issues if e.required]) > 1) == 8, "multi-finding reports"
    assert decoy_reasons(records) == (
        "descriptive_usage",
        "existing_obligation",
        "factual_policy_mention",
        "hedged_claim",
        "methods_language",
        "quoted_regulation",
        "skipped_section",
        "supported_recommendation",
        "technical_requirement",
        "term_of_art",
    )
    assert expects_edits(records) is False
    assert all(r.notes and r.target_answer is None for r in records), "notes replace the free-text target"


def test_every_listed_word_is_used_in_the_dataset():
    text = " ".join(r.document.lower() for r in load_inventory_records(DATASET))
    assert [w for w in LISTED_WORDS if w not in text] == []


def test_no_expected_issue_sits_in_a_skipped_section_and_every_skipped_decoy_does():
    for record in load_inventory_records(DATASET):
        skipped = skipped_lines(record.document)
        lines = record.document.split("\n")
        assert all(e.line not in skipped for e in record.expected_issues)
        for decoy in record.decoys:
            inside = any(decoy.anchor.lower() in lines[n - 1].lower() for n in skipped)
            assert inside == (decoy.reason == "skipped_section"), decoy.anchor


def test_a_false_positive_under_another_title_costs_precision():
    record = load_inventory_records(DATASET)[5]  # "It is urgent that policymakers act now ..."
    flagged = IssueItem(title="Advocacy Language Detected", severity="medium", start_line=9, end_line=9)
    extra = IssueItem(title="Trigger Words Detected", severity="low", start_line=9, end_line=9)
    values, _ = issue_detection_scores([flagged, extra], record, edits=False, one_to_one=True)
    assert values["recall"] == 1.0 and values["precision"] == 0.5


def test_task_composes_the_inventory_scorers_own_checks_and_judge():
    t = advocacy_tone_v2_e2e()
    assert len(t.scorer) == 4 and len(t.dataset) == 26
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "tone_checks", "judged_criteria"}
    assert list(t.metadata["metrics"]["issue_checks"]) == [
        "recall", "precision", "f0_5", "clean_document_untouched", "title_correct", "severity_correct", "anchor_in_range",
    ]
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__tone_checks__skipped_sections_untouched" in columns
    assert "score__judged_criteria__action_concrete" in columns
    assert "score__decoy_checks__no_fp_skipped_section" in columns


def test_judged_criteria_read_the_suggested_action():
    by_key = {c.key: c for c in JUDGE_CRITERIA}
    assert set(by_key) == {"action_concrete", "action_faithful"}
    assert all(c.scope == "expected" and c.applies_to is None for c in JUDGE_CRITERIA)
    assert by_key["action_concrete"].passage == "section" and by_key["action_faithful"].passage == "document"


def test_skipped_lines_cover_subsections_and_stop_at_the_next_section():
    skipped = skipped_lines(DOC)
    assert {6, 7, 9, 10, 11} <= skipped
    assert not {1, 3, 4, 12, 13} & skipped


def test_titles_and_severities_are_checked_over_every_reported_issue():
    issues = [
        IssueItem(title="Trigger Words Detected", severity="low", start_line=4, end_line=4),
        IssueItem(title="Advocacy Language Detected", severity="low", start_line=13, end_line=13),
        IssueItem(title="Certainty Language", severity="low", start_line=4, end_line=4),
    ]
    values, note = tone_scores(issues, INVENTORY)
    assert values["known_titles"] == 2 / 3
    assert values["severity_follows_title"] == 0.5
    assert "Certainty Language" in note and "'Advocacy Language Detected' at low" in note


def test_a_range_wider_than_one_line_is_counted():
    issues = [
        IssueItem(title="Trigger Words Detected", severity="low", start_line=4, end_line=4),
        IssueItem(title="Advocacy Language Detected", severity="medium", start_line=12, end_line=13),
    ]
    values, note = tone_scores(issues, INVENTORY)
    assert values["one_line_range"] == 0.5 and "12-13" in note


def test_an_issue_reaching_into_a_skipped_section_fails_the_sample():
    body = IssueItem(title="Trigger Words Detected", severity="low", start_line=4, end_line=4)
    nested = IssueItem(title="Trigger Words Detected", severity="low", start_line=11, end_line=11)
    spanning = IssueItem(title="Trigger Words Detected", severity="low", start_line=4, end_line=7)
    assert tone_scores([body], INVENTORY)[0]["skipped_sections_untouched"] == 1.0
    assert tone_scores([body, nested], INVENTORY)[0]["skipped_sections_untouched"] == 0.0
    assert tone_scores([spanning], INVENTORY)[0]["skipped_sections_untouched"] == 0.0


def test_tone_checks_are_nan_with_nothing_to_judge():
    values, _ = tone_scores([], INVENTORY)
    assert math.isnan(values["known_titles"]) and math.isnan(values["one_line_range"])
    assert math.isnan(values["severity_follows_title"])
    assert values["skipped_sections_untouched"] == 1.0, "a document with skipped sections left alone passes"
    plain = ResolvedInventory(document="# Report\n\n## Findings\nText.", expected_issues=[], decoys=[])
    assert math.isnan(tone_scores([], plain)[0]["skipped_sections_untouched"])
