"""The Figures & Tables Check eval's dataset and task, without a model."""

from pathlib import Path

from evals_inspectai.common.issue_checks import issue_detection_scores
from evals_inspectai.common.issue_inventory import decoy_reasons, expects_severities, load_inventory_records
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.figures_tables_check.figures_tables_check_e2e import figures_tables_check_e2e

DATASET = Path("evals_inspectai/e2e/figures_tables_check/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 22
    assert sum(1 for r in records if not r.expected_issues) == 8
    expected = [e for r in records for e in r.expected_issues]
    numbering = [e for e in expected if e.title == "Inconsistent Numbering"]
    assert len(numbering) == 8 and all(e.anchor is None for e in numbering), "numbering issues concern the whole sequence"
    assert expects_severities(records) is False
    assert decoy_reasons(records) == ("abbreviation_table", "appendix_prefix", "chapter_prefix", "conversion_artifact", "referenced_in_body")


def test_a_numbering_issue_counts_whatever_its_free_text_says():
    """The exact-title comparison this replaced scored a correct but differently worded finding as half wrong."""
    record = load_inventory_records(DATASET)[6]  # Figure 2 appears twice
    issue = IssueItem(title="Inconsistent Numbering: Figure 2 is used for two different figures", start_line=20, end_line=33)
    values, _ = issue_detection_scores([issue], record, edits=False, one_to_one=True, severities=False)
    assert values["recall"] == 1.0 and values["precision"] == 1.0


def test_task_composes_the_inventory_scorers_the_judge_and_the_image_check():
    t = figures_tables_check_e2e()
    assert len(t.scorer) == 4 and len(t.dataset) == 22
    assert set(t.metadata["metrics"]) == {"issue_checks", "decoy_checks", "model_graded_check", "tool_called"}
    assert "severity_correct" not in t.metadata["metrics"]["issue_checks"]
