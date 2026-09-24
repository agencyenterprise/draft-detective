"""The Narrative & Synthesis eval: its dataset, its task, the rule-reference check and which issues each judged criterion applies to."""

import math
from pathlib import Path

import pytest

from evals_inspectai.common.issue_inventory import (
    ResolvedInventory,
    ResolvedIssue,
    decoy_reasons,
    expects_edits,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.narrative_synthesis.criteria import JUDGE_CRITERIA, rule_reference_scores
from evals_inspectai.e2e.narrative_synthesis.narrative_synthesis_e2e import narrative_synthesis_e2e

DATASET = Path("evals_inspectai/e2e/narrative_synthesis/dataset.yaml")
EMPTY = ResolvedInventory(document="", expected_issues=[], decoys=[])


def _expected(title: str) -> ResolvedIssue:
    return ResolvedIssue(title=title, anchor="a", line=1, id="x")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 15
    expected = [e for r in records for e in r.expected_issues]
    assert {e.title for e in expected} == {
        "Data Without Synthesis",
        "Illogical Order",
        "Missing Framing: Why It Matters",
        "Missing Framing: What Is New",
        "Missing Framing: What Happens Next",
        "Restated Point",
    }
    assert sum(1 for r in records if not r.expected_issues) == 5, "five clean documents"
    assert {
        "interpreted_data",
        "interpretation_follows",
        "single_comparison",
        "table_or_figure",
        "methods_description",
        "appendix_data",
        "summary_restatement",
        "chapter_summary",
        "cross_reference",
        "signposting",
        "framing_elsewhere",
        "header_mismatch",
    } <= set(decoy_reasons(records))
    # The workflow proposes no edits, so the inventory says nothing about them.
    assert expects_edits(records) is False


def test_task_builds_without_edit_keys():
    task = narrative_synthesis_e2e()
    assert len(task.dataset) == 15
    assert not any(key.startswith("edit_") for key in task.metadata["metrics"]["issue_checks"])


def test_takeaway_criterion_applies_only_to_data_dumps():
    within = next(c for c in JUDGE_CRITERIA if c.key == "takeaway_within_evidence")
    specific = next(c for c in JUDGE_CRITERIA if c.key == "action_specific")
    assert within.applies_to is not None and within.applies_to(_expected("Data Without Synthesis"))
    assert not within.applies_to(_expected("Restated Point"))
    assert specific.applies_to is None
    assert all(c.scope == "expected" and c.passage == "section" for c in JUDGE_CRITERIA)


@pytest.mark.parametrize(
    "text",
    [
        "Per the editing rules, data should be interpreted.",
        "The guidelines ask that each paragraph earn its place.",
        "Per the guidelines, move Recommendations to the end.",
        "The writing guidelines call for a takeaway.",
        "Writing for Impact asks for a bottom line.",
        "This breaks the EEI style guide.",
    ],
)
def test_rule_reference_is_caught(text):
    values, explanation = rule_reference_scores([IssueItem(title="Data Without Synthesis", description=text)], EMPTY)
    assert values == {"no_rule_reference": 0.0}
    assert "Data Without Synthesis" in explanation


@pytest.mark.parametrize(
    "text",
    [
        "The reader has to work out what the wage figures show.",
        "The rule change in 2023 is listed without its effect on spending.",
        "State the takeaway the authors intend.",
        "Explain how the state guidelines changed eligibility.",
    ],
)
def test_plain_explanations_pass(text):
    values, _ = rule_reference_scores([IssueItem(title="Data Without Synthesis", suggested_action=text)], EMPTY)
    assert values == {"no_rule_reference": 1.0}


def test_rule_reference_is_a_share_of_reported_issues():
    issues = [
        IssueItem(title="Restated Point", description="Repeats Chapter 2."),
        IssueItem(title="Illogical Order", suggested_action="Per the guidelines, move Recommendations."),
    ]
    values, _ = rule_reference_scores(issues, EMPTY)
    assert values == {"no_rule_reference": 0.5}


def test_rule_reference_is_nan_when_nothing_reported():
    values, _ = rule_reference_scores([], EMPTY)
    assert math.isnan(values["no_rule_reference"])
