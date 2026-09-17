"""The Writing Consistency eval: its dataset, task and the workflow's own edit check."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import decoy_reasons, expects_edits, load_inventory_records
from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.e2e.writing_consistency.criteria import EXTRA_EDIT_CHECKS, JUDGE_CRITERIA, minimal_change
from evals_inspectai.e2e.writing_consistency.writing_consistency_e2e import writing_consistency_e2e

DATASET = Path("evals_inspectai/e2e/writing_consistency/dataset.yaml")


def _edit(original: str, replacement: str) -> ProposedEdit:
    return ProposedEdit(original_text=original, replacement_text=replacement, start_line=1, end_line=1, rationale="r")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 15
    expected = [e for r in records for e in r.expected_issues]
    assert len(expected) == 15
    prefixes = {e.title for e in expected}
    assert prefixes == {"Inconsistent Term", "Inconsistent", "Inconsistent Spelling", "Inconsistent Hyphenation", "Inconsistent Number Style", "Inconsistent Tense", "Inconsistent Tone", "House Style"}
    assert sum(1 for r in records if not r.expected_issues) == 5, "five clean documents"
    assert {"different_things", "glossed_short_form", "predicate_position", "quoted", "table"} <= set(decoy_reasons(records))
    assert expects_edits(records) is True
    # Tone shifts get no edit; everything else does.
    assert all((e.edit_expected is False) == (e.title == "Inconsistent Tone") for e in expected)


def test_minimal_change_accepts_a_swapped_variant_and_rejects_a_rewrite():
    assert minimal_change(_edit("Respondents rated scheduling as their main concern.", "Participants rated scheduling as their main concern.")) is True
    assert minimal_change(_edit("The council's decision-making followed the bylaws.", "The council's decisionmaking followed the bylaws.")) is True
    assert minimal_change(_edit("Principals report that recruiting was easier.", "Principals reported that recruiting was easier.")) is True
    assert minimal_change(_edit("Respondents rated scheduling as their main concern.", "Scheduling was the main concern participants raised.")) is False
    assert minimal_change(_edit("Respondents rated scheduling.", "")) is None


def test_task_composes_the_inventory_scorers_and_its_own_checks():
    t = writing_consistency_e2e()
    assert len(t.dataset) == 15 and len(t.scorer) == 4
    assert set(EXTRA_EDIT_CHECKS) == {"minimal_change"}
    assert {c.key for c in JUDGE_CRITERIA} == {"edit_meaning_preserved"}
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__consistency_edit_checks__edit_minimal_change" in columns
