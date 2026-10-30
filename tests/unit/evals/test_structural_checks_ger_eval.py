"""The Structural Checks (GER) eval: its dataset, its task, and where its criteria take their rules, without a model."""

from pathlib import Path

import pytest

from evals_inspectai.common.issue_checks import issue_detection_scores
from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_anchors,
    expects_edits,
    expects_severities,
    load_inventory_records,
)
from evals_inspectai.common.issue_judge import expected_prompt
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.structural_checks_ger.criteria import (
    AUTHOR_TITLE,
    JUDGE_CRITERIA,
    SKILL_FILE,
    part_of,
    skill_part,
)
from evals_inspectai.e2e.structural_checks_ger.structural_checks_ger_e2e import (
    structural_checks_ger_e2e,
)

DATASET = Path("evals_inspectai/e2e/structural_checks_ger/dataset.yaml")
RECORDS = load_inventory_records(DATASET)
MARSH_TWO_RULES = RECORDS[33]
EXPECTED = [e for r in RECORDS for e in r.expected_issues]


def test_dataset_is_well_formed():
    assert len(RECORDS) == 43
    assert sum(1 for r in RECORDS if not r.expected_issues) == 13
    assert len(EXPECTED) == 43 and sum(1 for e in EXPECTED if not e.required) == 7
    assert all(part_of(e) is not None for e in EXPECTED), "every title names a part"
    assert {part_of(e) for e in EXPECTED} == {"sections", "preface", "authors"}
    for e in EXPECTED:
        assert e.severity == ("high" if part_of(e) == "sections" else "medium")
    anchored = {e.title for e in EXPECTED if e.anchor}
    assert anchored == {AUTHOR_TITLE, "Missing Section: Appendix"}, (
        "only bios and the sentence citing a missing appendix are placed"
    )
    assert decoy_reasons(RECORDS) == (
        "abbreviation_periods",
        "professional_degree",
        "short_paragraph",
    )
    assert expects_anchors(RECORDS) and expects_severities(RECORDS)
    assert not expects_edits(RECORDS)
    assert all(r.notes and r.target_answer is None for r in RECORDS), (
        "every record says why it exists"
    )


def test_every_title_the_dataset_expects_is_one_the_skill_names():
    skill = SKILL_FILE.read_text()
    for e in EXPECTED:
        assert (e.title or "") in skill, e.title


def test_decoys_sit_on_bios_with_no_expected_issue():
    for record in RECORDS:
        lines = record.document.split("\n")
        expected_lines = {e.line for e in record.expected_issues if e.line is not None}
        for decoy in record.decoys:
            assert not any(
                decoy.anchor.lower() in lines[n - 1].lower() for n in expected_lines
            )


def test_one_author_failing_two_rules_is_one_issue():
    (expected,) = MARSH_TWO_RULES.expected_issues
    issue = IssueItem(
        title="Author Bio Issue: Kevin Marsh",
        severity="medium",
        start_line=expected.line,
        end_line=expected.line,
    )
    policy = MARSH_TWO_RULES.with_policy(edits=False, pairing="one_to_one")
    values, _ = issue_detection_scores([issue], policy)
    assert values["recall"] == 1.0 and values["precision"] == 1.0
    values, _ = issue_detection_scores([issue, issue], policy)
    assert values["precision"] == 0.5, "a second issue for the same author is extra"


def test_task_composes_the_scorers():
    t = structural_checks_ger_e2e()
    assert len(t.scorer) == 3 and len(t.dataset) == 43
    assert set(t.metadata["metrics"]) == {
        "issue_checks",
        "decoy_checks",
        "judged_criteria",
    }
    assert "anchor_in_range" in t.metadata["metrics"]["issue_checks"]
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__judged_criteria__bio_action" in columns


def test_each_criterion_carries_its_part_of_the_skill():
    parts = {
        "section_action_specific": 1,
        "section_action_grounded": 1,
        "preface_action": 2,
        "author_named": 3,
        "bio_action": 3,
    }
    assert {c.key for c in JUDGE_CRITERIA} == set(parts)
    for c in JUDGE_CRITERIA:
        assert skill_part(parts[c.key]) in c.criterion, c.key


def test_each_expected_issue_is_judged_by_its_parts_criteria():
    by_part = {
        "sections": ["section_action_specific", "section_action_grounded"],
        "preface": ["preface_action"],
        "authors": ["author_named", "bio_action"],
    }
    for e in EXPECTED:
        applies = [
            c.key
            for c in JUDGE_CRITERIA
            if c.applies_to is not None and c.applies_to(e)
        ]
        assert applies == by_part[part_of(e) or ""], e.id


def test_skill_part_stops_at_the_next_section():
    skill = (
        "# T\n\n## 1 — One\n\nfirst\n\n## 2 — Two\n\nsecond\n\n## Reporting\n\nlast\n"
    )
    assert skill_part(1, skill) == "## 1 — One\n\nfirst"
    assert skill_part(2, skill) == "## 2 — Two\n\nsecond"
    with pytest.raises(ValueError):
        skill_part(3, skill)


@pytest.mark.parametrize(
    "title",
    ["Author Bio Issue: Jane Smith", "Author Bio Issue", "Author Bio Issue: Marsh"],
)
def test_the_author_named_grader_sees_the_title_against_the_bio(title: str):
    """The inventory matches only "Author Bio Issue", so a wrong, missing or partial name
    reaches the grader, next to the bio whose author it should name."""
    (expected,) = MARSH_TWO_RULES.expected_issues
    (criterion,) = [c for c in JUDGE_CRITERIA if c.key == "author_named"]
    assert expected.line is not None
    issue = IssueItem(
        title=title,
        description="Two sentences and no degree.",
        start_line=expected.line,
        end_line=expected.line,
    )
    values, _ = issue_detection_scores(
        [issue], MARSH_TWO_RULES.with_policy(edits=False, pairing="one_to_one")
    )
    assert values["title_correct"] == 1.0, "the inventory alone cannot tell them apart"
    prompt = expected_prompt(criterion, expected, issue, MARSH_TWO_RULES.document)
    assert f"Title: {title}" in prompt
    assert "Kevin Marsh is a research associate" in prompt
