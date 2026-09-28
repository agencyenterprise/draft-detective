"""The About This (GER) eval: its dataset, its task, and its own deterministic checks, without a model."""

import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from inspect_ai.solver import TaskState

from evals_inspectai.common.issue_checks import issue_detection_scores, issues_from_state
from evals_inspectai.common.issue_inventory import (
    ResolvedInventory,
    decoy_reasons,
    expects_anchors,
    expects_edits,
    expects_severities,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.about_this_ger.about_this_ger_e2e import RESULTS, about_this_ger_e2e
from evals_inspectai.e2e.about_this_ger.criteria import (
    AUTHOR_TITLE,
    JUDGE_CRITERIA,
    NO_AUTHORS,
    NO_PREFACE,
    PREFACE_TITLES,
    about_scores,
    author_name,
    validator_of,
)

DATASET = Path("evals_inspectai/e2e/about_this_ger/dataset.yaml")
RECORDS = load_inventory_records(DATASET)
SMITH_FOUR_SENTENCES = RECORDS[8]
MARSH_TWO_RULES = RECORDS[14]
DOC = (
    "# Report\n\n## About the Authors\n\n"
    "Dr. Jane Smith is a senior researcher at the Coastal Policy Institute. She studies adaptation. She holds a Ph.D.\n\n"
    "John Doe is an economist at the Global Risk Centre. He studies risk. He holds an M.A.\n"
)
INVENTORY = ResolvedInventory(document=DOC, expected_issues=[], decoys=[])


def _state(preface: list[dict], authors: list[dict]) -> TaskState:
    completion = json.dumps({"preface_result": {"issues": preface}, "authors_result": {"issues": authors}})
    return cast(TaskState, SimpleNamespace(output=SimpleNamespace(completion=completion)))


def test_dataset_is_well_formed():
    assert len(RECORDS) == 24
    assert sum(1 for r in RECORDS if not r.expected_issues) == 5
    expected = [e for r in RECORDS for e in r.expected_issues]
    assert len(expected) == 23 and sum(1 for e in expected if not e.required) == 1
    authors = [e for e in expected if e.title == AUTHOR_TITLE]
    assert len(authors) == 9 and all(e.anchor for e in authors), "author issues are anchored on the bio"
    assert all(e.anchor is None for e in expected if e not in authors), "preface rules and missing sections are not"
    assert {e.title for e in expected} == {*PREFACE_TITLES, NO_PREFACE, NO_AUTHORS, AUTHOR_TITLE}
    assert all(e.severity == "medium" for e in expected)
    assert decoy_reasons(RECORDS) == ("abbreviation_periods", "professional_degree", "short_paragraph")
    assert expects_anchors(RECORDS) and expects_severities(RECORDS) and not expects_edits(RECORDS)
    assert all(r.notes and r.target_answer is None for r in RECORDS), "every record says why it exists"


def test_decoys_sit_on_bios_with_no_expected_issue():
    for record in RECORDS:
        lines = record.document.split("\n")
        expected_lines = {e.line for e in record.expected_issues if e.line is not None}
        for decoy in record.decoys:
            assert not any(decoy.anchor.lower() in lines[n - 1].lower() for n in expected_lines)


def test_both_validators_are_scored_together():
    state = _state([], [{"title": "Author Bio Issue: Dr. Jane Smith", "severity": "medium", "start_line": 17, "end_line": 17}])
    issues, error = issues_from_state(state, RESULTS)
    assert error is None
    values, _ = issue_detection_scores(issues, SMITH_FOUR_SENTENCES, edits=False, one_to_one=True)
    assert values["recall"] == 1.0 and values["title_correct"] == 1.0 and values["anchor_in_range"] == 1.0


def test_one_author_failing_two_rules_may_be_split_or_combined():
    line = MARSH_TWO_RULES.expected_issues[0].line
    issue = {"title": "Author Bio Issue: Kevin Marsh", "severity": "medium", "start_line": line, "end_line": line}
    split, _ = issues_from_state(_state([], [issue, {**issue, "description": "No degree."}]), RESULTS)
    combined, _ = issues_from_state(_state([], [issue]), RESULTS)
    for issues in (split, combined):
        values, _ = issue_detection_scores(issues, MARSH_TWO_RULES, edits=False, one_to_one=True)
        assert values["recall"] == 1.0 and values["precision"] == 1.0


def test_task_composes_the_scorers():
    t = about_this_ger_e2e()
    assert len(t.scorer) == 4 and len(t.dataset) == 24
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "about_checks", "judged_criteria"}
    assert list(t.metadata["metrics"]["issue_checks"]) == [
        "recall", "precision", "f0_5", "clean_document_untouched", "title_correct", "severity_correct", "anchor_in_range"
    ]
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__about_checks__known_titles" in columns and "score__judged_criteria__bio_action" in columns


def test_judged_criteria_split_preface_and_author_issues():
    by_key = {c.key: c for c in JUDGE_CRITERIA}
    assert by_key["preface_action"].passage == "document" and by_key["bio_action"].passage == "section"
    for record in RECORDS:
        for e in record.expected_issues:
            applies = [c.key for c in JUDGE_CRITERIA if c.applies_to is not None and c.applies_to(e)]
            assert applies == (["bio_action"] if e.title in (AUTHOR_TITLE, NO_AUTHORS) else ["preface_action"])


def test_author_names_and_validators_are_read_from_titles():
    assert author_name("Author Bio Issue: Dr. Jane Smith") == "jane smith"
    assert author_name("Preface: Defines Scope Missing") is None
    assert validator_of("Preface: Defines Scope Missing") == "preface" and validator_of(NO_PREFACE) == "preface"
    assert validator_of("Author Bio Issue: John Doe") == "authors" and validator_of("No “About the Authors” section found") == "authors"
    assert validator_of("Missing preface") is None


def test_titles_outside_the_skills_sets_are_counted():
    issues = [
        IssueItem(title="Preface: Defines Scope Missing"),
        IssueItem(title="Author Bio Issue: Dr. Jane Smith"),
        IssueItem(title="Author Bio Issue: Mary Major"),  # nobody of that name in the document
        IssueItem(title="Author Bio Issue: Smith"),  # not the full name
        IssueItem(title="Scope not defined"),
    ]
    values, note = about_scores(issues, INVENTORY)
    assert values["known_titles"] == 0.4
    assert "Mary Major" in note and "Scope not defined" in note


def test_every_reported_issue_must_be_medium():
    issues = [IssueItem(title=NO_PREFACE, severity="high"), IssueItem(title="Author Bio Issue: John Doe")]
    values, note = about_scores(issues, INVENTORY)
    assert values["severity_medium"] == 0.5 and "high" in note


def test_a_section_not_found_issue_stands_alone_in_its_validator():
    alone = [IssueItem(title=NO_PREFACE), IssueItem(title="Author Bio Issue: John Doe")]
    assert about_scores(alone, INVENTORY)[0]["not_found_alone"] == 1.0
    crowded = [IssueItem(title=NO_AUTHORS), IssueItem(title="Author Bio Issue: John Doe"), IssueItem(title=NO_PREFACE)]
    values, note = about_scores(crowded, INVENTORY)
    assert values["not_found_alone"] == 0.5 and "same validator" in note


def test_an_author_issue_names_the_author_of_its_bio():
    line = SMITH_FOUR_SENTENCES.expected_issues[0].line
    right = IssueItem(title="Author Bio Issue: Jane Smith", start_line=line, end_line=line)
    wrong = IssueItem(title="Author Bio Issue: John Doe", start_line=line, end_line=line)
    assert about_scores([right], SMITH_FOUR_SENTENCES)[0]["author_named"] == 1.0
    values, note = about_scores([wrong], SMITH_FOUR_SENTENCES)
    assert values["author_named"] == 0.0 and "does not name the author" in note


def test_own_checks_are_nan_with_nothing_to_judge():
    values, _ = about_scores([], INVENTORY)
    assert all(math.isnan(v) for v in values.values())
    values, _ = about_scores([IssueItem(title="Preface: Defines Scope Missing")], INVENTORY)
    assert values["known_titles"] == 1.0 and math.isnan(values["not_found_alone"]) and math.isnan(values["author_named"])
