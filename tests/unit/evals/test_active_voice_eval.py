"""What the Active Voice eval adds on top of the generic inventory scorer."""

from pathlib import Path

from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.common.issue_inventory import (
    ResolvedIssue,
    decoy_reasons,
    load_inventory_records,
)
from evals_inspectai.e2e.active_voice.criteria import (
    EXTRA_EDIT_CHECKS,
    JUDGE_CRITERIA,
    passive_count,
    removes_passive,
)

DATASET = Path("evals_inspectai/e2e/active_voice/dataset.yaml")


def _edit(original: str, replacement: str) -> ProposedEdit:
    return ProposedEdit(original_text=original, replacement_text=replacement, start_line=1, end_line=1, rationale="r")


def test_removes_passive_wants_fewer_be_participle_constructions():
    assert removes_passive(_edit("Data were collected by the team.", "The team collected data.")) is True
    assert removes_passive(_edit("Data were collected by the team.", "Data were collected by the team from three sites.")) is False
    # A replacement that clears one passive but keeps another pre-existing one still counts as progress.
    assert removes_passive(_edit("Data were collected and results were shared.", "We collected data and results were shared.")) is True


def test_passive_count_sees_irregular_participles_and_intervening_adverbs():
    assert passive_count("Non-respondents were sent two reminders.") == 1
    assert passive_count("Off-grid options were not considered.") == 1
    assert passive_count("The notion was first proposed in 1990 and is widely regarded as settled.") == 2
    assert passive_count("The framework was developed after feedback.") == 1
    assert passive_count("Those decisions are being made now; the plan has been sent.") == 2
    assert passive_count("We collected data. Results are even better. The sites are open.") == 0


def test_removes_passive_gives_no_credit_where_it_cannot_see_a_passive_removed():
    # A still-passive rewrite fails rather than passing on a zero-zero count.
    assert removes_passive(_edit("Non-respondents were sent two reminders.", "Two reminders were sent to non-respondents.")) is False
    assert removes_passive(_edit("Off-grid options were not considered.", "Off-grid options were not considered.")) is False
    # An original the heuristic sees no passive in is not assessable, so it is neither passed nor failed.
    assert removes_passive(_edit("The evaluation will assess fidelity.", "The research team will assess fidelity.")) is None


def test_extra_edit_checks_are_registered_under_the_expected_key():
    assert set(EXTRA_EDIT_CHECKS) == {"removes_passive"}


def test_actor_criterion_applies_only_to_passive_issues_without_an_edit():
    actor = next(c for c in JUDGE_CRITERIA if c.key == "unknown_actor_asked_not_guessed")
    assert actor.scope == "expected" and actor.applies_to is not None
    base = {"id": "f", "anchor": "x", "line": 1}
    assert actor.applies_to(ResolvedIssue(title="Passive Voice", edit_expected=False, **base))
    assert not actor.applies_to(ResolvedIssue(title="Passive Voice", edit_expected=True, **base))
    assert not actor.applies_to(ResolvedIssue(title="Ambiguous Actor", edit_expected=False, **base))


def test_every_metric_has_a_description_for_the_log_viewer():
    from evals_inspectai.common.issue_checks import DETECTION_KEYS, EDIT_KEYS
    from evals_inspectai.e2e.active_voice.active_voice_e2e import metric_descriptions

    reasons = list(decoy_reasons(load_inventory_records(DATASET)))
    described = metric_descriptions(reasons)
    assert set(described["issue_checks"]) == set(DETECTION_KEYS) | set(EDIT_KEYS)
    assert set(described["decoy_checks"]) == {f"no_fp_{r}" for r in reasons}
    assert set(described["active_voice_edit_checks"]) == {f"edit_{name}" for name in EXTRA_EDIT_CHECKS}
    assert set(described["judged_criteria"]) == {c.key for c in JUDGE_CRITERIA}


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) >= 19
    assert any(not r.expected_issues for r in records) and any(len(r.expected_issues) >= 5 for r in records)
    assert all(f.line >= 1 for r in records for f in r.expected_issues)
    assert "stative" in decoy_reasons(records)
    # Every expected says whether an edit is expected, so the edit layer has something to check.
    assert all(f.edit_expected is not None for r in records for f in r.expected_issues if f.required)
