"""The Concision & Precision eval: its dataset, task and the workflow's own edit check."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import decoy_reasons, expects_edits, load_inventory_records
from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.e2e.concision_precision.concision_precision_e2e import concision_precision_e2e
from evals_inspectai.e2e.concision_precision.criteria import EXTRA_EDIT_CHECKS, JUDGE_CRITERIA, no_added_passive

DATASET = Path("evals_inspectai/e2e/concision_precision/dataset.yaml")


def _edit(original: str, replacement: str) -> ProposedEdit:
    return ProposedEdit(original_text=original, replacement_text=replacement, start_line=1, end_line=1, rationale="r")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 15
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 19
    titles = {e.title for e in expected}
    assert titles == {"Wordy Construction", "Run-On Sentence", "Throat-Clearing", "Vague Reference", "Empty Framing", "Obvious Statement"}
    assert sum(1 for r in records if not r.expected_issues) == 5, "five clean documents"
    assert {"signposting", "qualifier", "hedge", "compound", "topic_sentence"} <= set(decoy_reasons(records))
    assert expects_edits(records) is True
    # Every expected says whether an edit is expected, except an Obvious Statement, where deleting
    # the sentence and asking for the deeper point are both acceptable fixes.
    assert all(e.edit_expected is not None for e in expected if e.title != "Obvious Statement")


def test_no_added_passive_lets_tightening_through_but_not_a_new_passive():
    assert no_added_passive(_edit("In order to rank the sites, we combined the data.", "To rank the sites, we combined the data.")) is True
    assert no_added_passive(_edit("We ranked the sites by five criteria.", "The sites were ranked by five criteria.")) is False
    assert no_added_passive(_edit("The data were collected weekly.", "The data were collected weekly by the team.")) is True, "no more passives than before"
    assert no_added_passive(_edit("This is a complex issue.", "")) is None, "a deletion has nothing to assess"


def test_task_composes_the_inventory_scorers_and_its_own_checks():
    t = concision_precision_e2e()
    assert len(t.dataset) == 15 and len(t.scorer) == 4
    assert set(EXTRA_EDIT_CHECKS) == {"no_added_passive"}
    assert {c.key for c in JUDGE_CRITERIA} == {"edit_meaning_preserved", "edit_reads_well"}
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__concision_edit_checks__edit_no_added_passive" in columns
    assert columns.index("score__judged_criteria__edit_reads_well") < columns.index("error")
