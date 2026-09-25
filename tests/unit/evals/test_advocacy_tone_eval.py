"""The Advocacy & Tone v2 eval's dataset and task, without a model."""

from collections import Counter
from pathlib import Path

from evals_inspectai.common.issue_checks import issue_detection_scores
from evals_inspectai.common.issue_inventory import decoy_reasons, expects_edits, load_inventory_records
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.advocacy_tone_v2.advocacy_tone_v2_e2e import advocacy_tone_v2_e2e

DATASET = Path("evals_inspectai/e2e/advocacy_tone_v2/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 14
    required = [e for r in records for e in r.expected_issues if e.required]
    assert Counter(e.title for e in required) == {"Advocacy Language Detected": 6, "Trigger Words Detected": 1, "Subjective Tone Detected": 1}
    assert all(e.severity == ("low" if e.title == "Trigger Words Detected" else "medium") for r in records for e in r.expected_issues)
    assert sum(1 for r in records if not r.expected_issues) == 6
    assert decoy_reasons(records) == ("existing_obligation", "methods_language", "quoted_regulation", "technical_requirement", "term_of_art")
    assert expects_edits(records) is False
    assert all(r.target_answer for r in records)


def test_a_false_positive_under_another_title_costs_precision():
    """The count-per-title comparison this replaced only looked at the titles a sample listed."""
    record = load_inventory_records(DATASET)[5]  # "It is urgent that policymakers act now ..."
    flagged = IssueItem(title="Advocacy Language Detected", severity="medium", start_line=9, end_line=9)
    extra = IssueItem(title="Trigger Words Detected", severity="low", start_line=9, end_line=9)
    values, _ = issue_detection_scores([flagged, extra], record, edits=False, one_to_one=True)
    assert values["recall"] == 1.0 and values["precision"] == 0.5


def test_task_composes_the_inventory_scorers_and_the_judge():
    t = advocacy_tone_v2_e2e()
    assert len(t.scorer) == 3 and len(t.dataset) == 14
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "model_graded_check"}
    assert t.dataset[0].target, "the judge reads the record's target_answer"
