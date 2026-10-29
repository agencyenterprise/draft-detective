"""The Sentence Structure eval: its dataset and task."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_edits,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.e2e.sentence_structure.criteria import (
    EXTRA_EDIT_CHECKS,
    JUDGE_CRITERIA,
    one_sentence,
)
from evals_inspectai.e2e.sentence_structure.sentence_structure_e2e import (
    sentence_structure_e2e,
)

DATASET = Path("evals_inspectai/e2e/sentence_structure/dataset.yaml")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 15
    expected = [e for r in records for e in r.expected_issues if e.required]
    assert len(expected) == 28
    assert {e.title for e in expected} == {
        "Incomplete Sentence",
        "Broken Shared Construction",
        "Faulty Parallelism",
        "Indirect Summary Sentence",
    }
    assert sum(1 for r in records if not r.expected_issues) == 3, (
        "three clean documents"
    )
    assert {
        "grammatical_shared",
        "correct_correlative",
        "emergent_finding",
        "direct_leadin",
        "other_check",
    } <= set(decoy_reasons(records))
    assert expects_edits(records) is True


def test_long_report_plants_a_pattern_in_its_last_chapter():
    records = load_inventory_records(DATASET)
    long_report = max(records, key=lambda r: len(r.document))
    lines = [
        e.line for e in long_report.expected_issues if e.required and e.line is not None
    ]
    assert max(lines) > 0.9 * len(long_report.document.splitlines())


def test_task_composes_the_inventory_scorers_and_its_own_checks():
    t = sentence_structure_e2e()
    assert len(t.dataset) == 15 and len(t.scorer) == 4
    # One issue per sentence: a report on a shared paragraph line covers only one expected sentence.
    assert all(
        s.metadata["inventory"]["policy"]["pairing"] == "one_to_one" for s in t.dataset
    )
    assert set(EXTRA_EDIT_CHECKS) == {"one_sentence", "no_added_passive"}
    assert {c.key for c in JUDGE_CRITERIA} == {
        "edit_meaning_preserved",
        "edit_reads_well",
    }
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__sentence_structure_edit_checks__edit_no_added_passive" in columns


def _edit(original: str) -> ProposedEdit:
    return ProposedEdit(
        original_text=original,
        replacement_text="r",
        start_line=1,
        end_line=1,
        rationale="r",
    )


def test_one_sentence_rejects_an_edit_that_spans_two_sentences():
    assert one_sentence(_edit("The terms for each round shown in Table 1."))
    assert one_sentence(_edit("Costs rose 2.5 percent (Smith, 2024)."))
    assert not one_sentence(
        _edit(
            "A summary is shown in Figure 4. This summary suggests that challenges remain."
        )
    )
    assert not one_sentence(_edit('Staff said "it worked." Most sites agreed.'))
    assert not one_sentence(_edit("Costs rose. *Most* sites agreed."))
    assert not one_sentence(_edit("Costs rose. [Table 2](#t2) shows why."))
    assert one_sentence(_edit("training them")), "a phrase inside one sentence"
