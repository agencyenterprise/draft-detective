"""The Inference Validation eval: its dataset, its task, and its reporting-contract checks."""

import math
from pathlib import Path

import pytest

from evals_inspectai.common.issue_inventory import (
    ResolvedInventory,
    expects_edits,
    expects_severities,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.inference_validation_v2.criteria import (
    JUDGE_CRITERIA,
    TITLE,
    inference_scores,
    key_sentence,
)
from evals_inspectai.e2e.inference_validation_v2.inference_validation_v2_e2e import inference_validation_v2_e2e

DATASET = Path("evals_inspectai/e2e/inference_validation_v2/dataset.yaml")
DOC = "# Memo\n\nThree customers complained last week. Therefore, reliability is poor across the\nentire customer base.\n"
INVENTORY = ResolvedInventory(document=DOC, expected_issues=[], decoys=[])
LONG = "## Key Sentence\n\n> Therefore, reliability is poor across the entire customer base.\n\n## Detailed Analysis\n\nThree is too few."


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 32
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 26
    assert [e.id for e in expected if not e.required] == ["collapse_claim"]
    assert all(e.title == TITLE and e.anchor and e.rationale for e in expected), "anchored, titled, with the labelled flaw"
    assert sum(1 for r in records if not r.expected_issues) == 9
    assert all(d.title in (TITLE, None) for r in records for d in r.decoys)
    assert expects_severities(records) is False and expects_edits(records) is False


def test_decoys_bracketing_an_expected_line_are_untitled():
    """A titled decoy is flagged by an issue bracketing its line, so one sharing a line with
    an expected issue would be flagged by the correct report of that issue."""
    for record in load_inventory_records(DATASET):
        lines = record.document.split("\n")
        expected_lines = {e.line for e in record.expected_issues}
        for decoy in record.decoys:
            on = next(n for n, line in enumerate(lines, 1) if decoy.anchor.lower() in line.lower())
            assert decoy.title is None or on not in expected_lines, decoy.anchor


def test_task_scores_detection_without_severity_and_the_contract():
    t = inference_validation_v2_e2e()
    assert len(t.dataset) == 32 and len(t.scorer) == 4
    assert "severity_correct" not in t.metadata["metrics"]["issue_checks"]
    assert set(t.metadata["metrics"]["inference_checks"]) == {"no_informational", "title_names_flaw", "key_sentence_quoted"}


def test_the_flaw_criterion_reads_the_analysis_against_the_labelled_flaw():
    flaw, repair = JUDGE_CRITERIA
    assert (flaw.reads, flaw.reference) == ("analysis", True)
    assert (repair.reads, repair.reference) == ("suggested_action", False)


def test_key_sentence_is_the_quote_under_its_heading():
    assert key_sentence(LONG) == "Therefore, reliability is poor across the entire customer base."
    assert key_sentence("## Detailed Analysis\n\n> not a key sentence") is None
    assert key_sentence("## Key Sentence\n\nNo blockquote here.") is None


def test_contract_checks_read_every_reported_issue():
    good = IssueItem(title="Invalid Inference: Hasty generalization", severity="high", long_description=LONG)
    informational = IssueItem(title="Invalid Inference: Sound", severity="none", long_description=LONG)
    unlabelled = IssueItem(title="Invalid Inference", severity="medium", long_description="## Key Sentence\n\n> Reliability is excellent.")
    values, note = inference_scores([good, informational, unlabelled], INVENTORY)
    assert values == pytest.approx({"no_informational": 2 / 3, "title_names_flaw": 2 / 3, "key_sentence_quoted": 2 / 3})
    assert "informational" in note and "without the flaw label" in note and "no verbatim key sentence" in note


def test_contract_checks_are_nan_with_nothing_reported():
    values, _ = inference_scores([], INVENTORY)
    assert all(math.isnan(v) for v in values.values())
