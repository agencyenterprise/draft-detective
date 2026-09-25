"""The About This (GER) eval's dataset and task, without a model."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from inspect_ai.solver import TaskState

from evals_inspectai.common.issue_checks import issue_detection_scores, issues_from_state
from evals_inspectai.common.issue_inventory import load_inventory_records
from evals_inspectai.e2e.about_this_ger.about_this_ger_e2e import RESULTS, about_this_ger_e2e

DATASET = Path("evals_inspectai/e2e/about_this_ger/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 13
    assert not records[0].expected_issues, "the seed document passes every rule"
    assert all(len(r.expected_issues) == 1 for r in records[1:]), "every other sample breaks exactly one rule"
    expected = [e for r in records for e in r.expected_issues]
    authors = [e for e in expected if e.title == "Author Bio Issue"]
    assert len(authors) == 4 and all(e.anchor for e in authors), "author issues are anchored on the bio"
    assert all(e.anchor is None for e in expected if e not in authors), "preface rules and missing sections are not"
    assert all(e.severity == "medium" for e in expected)


def test_both_validators_are_scored_together():
    record = load_inventory_records(DATASET)[8]  # Jane Smith's bio has four sentences
    state = cast(TaskState, SimpleNamespace(output=SimpleNamespace(completion=json.dumps({
        "preface_result": {"issues": []},
        "authors_result": {"issues": [{"title": "Author Bio Issue: Dr. Jane Smith", "severity": "medium", "start_line": 17, "end_line": 17}]},
    }))))
    issues, error = issues_from_state(state, RESULTS)
    assert error is None
    values, _ = issue_detection_scores(issues, record, edits=False, one_to_one=True)
    assert values["recall"] == 1.0 and values["title_correct"] == 1.0 and values["anchor_in_range"] == 1.0


def test_task_composes_the_inventory_scorer_and_the_judge():
    t = about_this_ger_e2e()
    assert len(t.scorer) == 2 and len(t.dataset) == 13
    assert set(t.metadata["metrics"]) == {"issue_checks", "model_graded_check"}
