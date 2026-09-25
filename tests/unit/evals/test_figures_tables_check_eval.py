"""The Figures & Tables Check eval: its dataset, its task, and its own deterministic checks."""

import math
from pathlib import Path

from evals_inspectai.common.issue_checks import issue_detection_scores
from evals_inspectai.common.issue_inventory import (
    ResolvedInventory,
    ResolvedIssue,
    decoy_reasons,
    expects_edits,
    expects_severities,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.figures_tables_check.criteria import (
    ELEMENT_RULES,
    JUDGE_CRITERIA,
    NUMBERING,
    TITLE_PREFIXES,
    label,
    title_parts,
    title_scores,
)
from evals_inspectai.e2e.figures_tables_check.figures_tables_check_e2e import figures_tables_check_e2e

DATASET = Path("evals_inspectai/e2e/figures_tables_check/dataset.yaml")
SEVERITY = {"Missing Figure/Table": "high", "Unreferenced Figure/Table": "medium", "Inconsistent Numbering": "medium"}

DOC = "# Report\n\nAs Fig. 2 shows, visits rose.\n\n**Fig. 2: Visits by group**\n\nTable 3 is cited but absent.\n"


def _inventory(*expected: ResolvedIssue) -> ResolvedInventory:
    return ResolvedInventory(document=DOC, expected_issues=list(expected), decoys=[])


UNREFERENCED = ResolvedIssue(id="fig_2", title="Unreferenced Figure/Table", anchor="Fig. 2: Visits by group", line=5)
MISSING = ResolvedIssue(id="table_3", title="Missing Figure/Table", anchor="Table 3 is cited but absent", line=7)


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 33
    assert sum(1 for r in records if not r.expected_issues) == 11
    expected = [e for r in records for e in r.expected_issues]
    assert all(e.title is not None and e.title.split(":")[0] in TITLE_PREFIXES for e in expected)
    numbering = [e for e in expected if e.title == NUMBERING]
    assert len(numbering) == 12 and all(e.anchor is None for e in numbering), "numbering issues concern the whole sequence"
    # Severity where the issues skill's scale names the finding, and never for a missing title.
    assert all(e.severity == SEVERITY.get((e.title or "").split(":")[0]) for e in expected)
    assert expects_severities(records) is True and expects_edits(records) is False
    assert decoy_reasons(records) == (
        "abbreviated_reference",
        "abbreviation_table",
        "appendix_prefix",
        "captioned_unnumbered",
        "chapter_prefix",
        "conversion_artifact",
        "parenthetical_reference",
        "plural_reference",
        "referenced_in_body",
        "supplementary_prefix",
    )
    assert all(r.notes for r in records), "every record says why it exists"
    assert all(r.target_answer is None for r in records), "the free-text target was replaced by judged criteria"


def test_every_anchored_element_issue_names_its_label_in_the_anchor_or_is_unlabelled():
    """The label check reads the expected label from the anchor, so an anchor that names a
    label must name the right one first; only unlabelled elements carry none."""
    records = load_inventory_records(DATASET)
    anchored = [e for r in records for e in r.expected_issues if e.anchor and e.title in ELEMENT_RULES]
    unlabelled = [e.id for e in anchored if label(e.anchor or "") is None]
    assert sorted(unlabelled) == ["referrals_figure_unreferenced", "unlabeled_table", "unlabeled_table_unreferenced"]


def test_a_numbering_issue_counts_whatever_its_free_text_says():
    """The exact-title comparison this replaced scored a correct but differently worded finding as half wrong."""
    record = load_inventory_records(DATASET)[6]  # Figure 2 appears twice
    issue = IssueItem(
        title="Inconsistent Numbering: Figure 2 is used for two different figures", severity="medium", start_line=20, end_line=33
    )
    values, _ = issue_detection_scores([issue], record, edits=False, one_to_one=True)
    assert values["recall"] == 1.0 and values["precision"] == 1.0 and values["severity_correct"] == 1.0


def test_task_composes_the_inventory_scorers_own_checks_judge_and_image_check():
    t = figures_tables_check_e2e()
    assert len(t.scorer) == 5 and len(t.dataset) == 33
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "title_checks", "judged_criteria", "tool_called"}
    assert list(t.metadata["metrics"]["issue_checks"]) == [
        "recall",
        "precision",
        "f0_5",
        "clean_document_untouched",
        "title_correct",
        "severity_correct",
        "anchor_in_range",
    ]
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__title_checks__title_names_element" in columns and "score__judged_criteria__action_concrete" in columns


def test_judged_criteria_read_the_suggested_action_against_the_whole_report():
    assert {c.key for c in JUDGE_CRITERIA} == {"action_concrete", "action_grounded"}
    assert all(c.scope == "expected" and c.passage == "document" and c.applies_to is None for c in JUDGE_CRITERIA)


def test_labels_are_read_whatever_their_spelling():
    assert label("As Fig. 2 shows") == label("**FIGURE 2**") == ("figure", "2")
    assert label("Table S.1: rates") == label("(Table S1)") == ("table", "S1")
    assert label("Figure A.3") == ("figure", "A3") and label("TABLE 3.1") == ("table", "3.1")
    assert label("Figures 1 and 2") is None and label("Figure: Referrals by reason") is None


def test_title_parts_split_the_rule_from_the_placeholder():
    assert title_parts("Figure/Table Missing Title: Figure 2") == ("Figure/Table Missing Title", "Figure 2")
    assert title_parts("missing figure/table: Table S2") == ("Missing Figure/Table", "Table S2")
    assert title_parts("Missing Title: Figure 2") is None


def test_titles_outside_the_skills_set_are_counted():
    issues = [
        IssueItem(title="Inconsistent Numbering: Figure 3 skipped"),
        IssueItem(title="Missing Caption: Figure 2"),
        IssueItem(title="Unreferenced Figure/Table: [label]"),
        IssueItem(title="Missing Figure/Table:"),
    ]
    values, note = title_scores(issues, _inventory())
    assert values["known_titles"] == 0.25
    assert "Missing Caption: Figure 2" in note


def test_a_detected_element_issue_must_name_its_label():
    right = [
        IssueItem(title="Unreferenced Figure/Table: Figure 2", start_line=5, end_line=5),
        IssueItem(title="Missing Figure/Table: Table 3", start_line=7, end_line=7),
    ]
    values, _ = title_scores(right, _inventory(UNREFERENCED, MISSING))
    assert values["title_names_element"] == 1.0
    wrong = [
        IssueItem(title="Unreferenced Figure/Table: Figure 2", start_line=5, end_line=5),
        IssueItem(title="Missing Figure/Table: Table 4", start_line=7, end_line=7),
    ]
    values, note = title_scores(wrong, _inventory(UNREFERENCED, MISSING))
    assert values["title_names_element"] == 0.5 and "table_3" in note


def test_own_checks_are_nan_with_nothing_to_judge():
    values, _ = title_scores([], _inventory(MISSING))
    assert math.isnan(values["known_titles"]) and math.isnan(values["title_names_element"])
    numbering = ResolvedIssue(id="skip", title=NUMBERING)
    values, _ = title_scores([IssueItem(title="Inconsistent Numbering: Table 3 skipped")], _inventory(numbering))
    assert values["known_titles"] == 1.0 and math.isnan(values["title_names_element"])
