"""The Audience Fit eval: its dataset, task and which issues each judged criterion applies to."""

from pathlib import Path

from evals_inspectai.common.issue_inventory import (
    ResolvedIssue,
    decoy_reasons,
    expects_edits,
    expects_titles,
    load_inventory_records,
)
from evals_inspectai.e2e.audience_fit.audience_fit_e2e import audience_fit_e2e
from evals_inspectai.e2e.audience_fit.criteria import JUDGE_CRITERIA

DATASET = Path("evals_inspectai/e2e/audience_fit/dataset.yaml")


def _expected(title: str) -> ResolvedIssue:
    return ResolvedIssue(title=title, anchor="a", line=1, id="x")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 15
    expected = [e for r in records for e in r.expected_issues]
    assert {e.title for e in expected} == {
        "Target Audience Missing",
        "Target Audience Too Vague",
        "Target Audience Conflict",
        "Technical Language",
        "Technical Language: Move to Appendix",
    }
    assert sum(1 for r in records if not r.expected_issues) == 6, "six clean documents"
    assert {
        "specific_audience",
        "reworded_audience",
        "technical_audience",
        "audience_vocabulary",
        "explained_term",
        "appendix",
        "appendix_pointer",
        "quoted",
    } <= set(decoy_reasons(records))
    # The workflow proposes no edits, so the inventory expects none and names every title.
    assert expects_edits(records) is False
    assert expects_titles(records) is True
    assert all(e.edit_expected is None and e.edit is None for e in expected)


def test_each_criterion_applies_to_its_own_issues():
    by_key = {c.key: c for c in JUDGE_CRITERIA}
    plain, audience = by_key["action_plain_alternative"], by_key["action_specific_audience"]
    assert plain.applies_to is not None and audience.applies_to is not None
    assert plain.applies_to(_expected("Technical Language"))
    assert plain.applies_to(_expected("Technical Language: Move to Appendix"))
    assert not plain.applies_to(_expected("Target Audience Missing"))
    assert audience.applies_to(_expected("Target Audience Missing"))
    assert audience.applies_to(_expected("Target Audience Too Vague"))
    # A conflict is settled by the author, not by a proposed audience.
    assert not audience.applies_to(_expected("Target Audience Conflict"))
    assert not audience.applies_to(_expected("Technical Language"))


def test_task_composes_the_inventory_scorers_and_its_judged_criteria():
    t = audience_fit_e2e()
    assert len(t.dataset) == 15 and len(t.scorer) == 3
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__judged_criteria__action_plain_alternative" in columns
    assert "score__decoy_checks__no_fp_technical_audience" in columns
    # No edits are expected, so no edit-hygiene column is emitted.
    assert not any("edit_" in c for c in columns)
