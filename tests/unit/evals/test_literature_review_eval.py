"""The Literature Review eval: its dataset and its task."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import expects_edits, expects_severities, expects_titles, load_inventory_records
from evals_inspectai.e2e.literature_review_v2.criteria import JUDGE_CRITERIA
from evals_inspectai.e2e.literature_review_v2.literature_review_v2_e2e import literature_review_v2_e2e

DATASET = Path("evals_inspectai/e2e/literature_review_v2/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 12
    required = [e for r in records for e in r.expected_issues if e.required]
    assert len(required) == 25 and all(e.anchor and e.rationale for e in required), "anchored, with the labelled literature"
    assert sum(1 for r in records if not r.expected_issues) == 2
    assert sum(1 for r in records if r.publication_date) == 7
    assert not (expects_titles(records) or expects_severities(records) or expects_edits(records))


def test_decoys_sit_on_lines_of_their_own():
    """Issues are matched by line, so a decoy sharing a line with a claim would stand for it."""
    for record in load_inventory_records(DATASET):
        lines = record.document.split("\n")
        claimed = {e.line for e in record.expected_issues}
        for decoy in record.decoys:
            assert next(n for n, line in enumerate(lines, 1) if decoy.anchor in line) not in claimed, decoy.anchor


def test_task_scores_detection_sources_and_two_judged_criteria():
    t = literature_review_v2_e2e()
    assert len(t.dataset) == 12 and len(t.scorer) == 4
    assert "title_correct" not in t.metadata["metrics"]["issue_checks"]
    assert set(t.metadata["metrics"]["source_checks"]) == {"cites_source", "sources_in_window", "report_lists_sources"}
    source, action = JUDGE_CRITERIA
    assert (source.reads, source.reference) == ("analysis", True) and action.reads == "suggested_action"
