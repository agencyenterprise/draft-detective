"""The generic issue checks (any workflow that reports issues), without a model.

Each test pins a way a count-based scorer could not tell right from wrong: a
expected hit on the wrong paragraph, a decoy flagged, an edit that drops a
number or strands a comma, an edit attached where none is expected.
"""

import math
from pathlib import Path

import pytest

from evals_inspectai.common.simple_deep_agent_types import IssueItem, ProposedEdit
from evals_inspectai.common.issue_checks import (
    DETECTION_KEYS,
    EDIT_KEYS,
    decoy_hits,
    decoy_scores,
    issue_detection_scores,
    edit_checks,
    extra_edit_scores,
    hit_issue,
)
from evals_inspectai.common.issue_inventory import (
    Decoy,
    InventoryRecord,
    ResolvedIssue,
    ResolvedInventory,
    locate_anchor,
    overlaps,
    resolve_record,
)

DOC = "# Title\n\n## Methods\n\nData were collected from 3 sites by the field team. We then coded the notes.\n\n## Results\n\nThe scope is limited to urban sites. Findings are listed in Appendix A.\n"
LINES = DOC.split("\n")
REASONS = ("stative", "active", "generic")


def _expected(**kw) -> ResolvedIssue:
    base = {"id": "f", "title": "Passive Voice", "anchor": "Data were collected", "line": 5}
    return ResolvedIssue(**{**base, **kw})


def _issue(title="Passive Voice", description="", start=5, end=5, edits=(), suggested=None, severity="low") -> IssueItem:
    return IssueItem(title=title, description=description, severity=severity, start_line=start, end_line=end, edits=list(edits), suggested_action=suggested)


def _inventory(expected=(), decoys=()) -> ResolvedInventory:
    return ResolvedInventory(document=DOC, expected_issues=list(expected), decoys=list(decoys))


def _edit(original, replacement, line=5) -> ProposedEdit:
    return ProposedEdit(original_text=original, replacement_text=replacement, start_line=line, end_line=line, rationale="r")


# --- anchors -------------------------------------------------------------------


def test_anchor_resolves_to_its_line_ignoring_quote_style_and_case():
    assert locate_anchor(LINES, "data WERE collected", "f") == 5


def test_anchor_must_be_unique():
    with pytest.raises(ValueError, match="exactly one line"):
        locate_anchor(LINES + ["Data were collected again."], "Data were collected", "f")


def test_missing_anchor_is_an_error():
    with pytest.raises(ValueError, match="not found"):
        locate_anchor(LINES, "never in the document", "f")


def test_resolve_record_fills_lines_and_checks_decoys():
    record = InventoryRecord(
        input=DOC,
        expected_issues=[{"id": "a", "title": "Passive Voice", "anchor": "Findings are listed"}],
        decoys=[{"anchor": "is limited to", "reason": "stative"}],
    )
    assert resolve_record(record).expected_issues[0].line == 9
    with pytest.raises(ValueError, match="decoy"):
        resolve_record(InventoryRecord(input=DOC, decoys=[{"anchor": "absent text", "reason": "other"}]))


def test_overlaps_pairs_a_quote_with_its_sentence():
    assert overlaps("Data were collected", "Data were collected from 3 sites by the field team.")
    assert overlaps("collected from 3 sites by the team", "Data were collected from 3 sites by the field team.")
    assert not overlaps("We then coded the notes.", "Data were collected from 3 sites by the field team.")


# --- detection ------------------------------------------------------------------


def test_hit_requires_title_and_anchor_or_line():
    f = _expected()
    assert hit_issue(f, [_issue(description="uses passive voice: “Data were collected from 3 sites”", start=1, end=1)]) == 0
    assert hit_issue(f, [_issue(description="no quote", start=5, end=5)]) == 0
    assert hit_issue(f, [_issue(title="Other", description="“Data were collected”", start=1, end=1)]) == 0
    assert hit_issue(f, [_issue(title="Other", description="no quote", start=5, end=5)]) is None


def test_two_expected_issues_may_hit_one_paragraph_issue():
    f1 = _expected(id="a", anchor="Data were collected")
    f2 = _expected(id="b", anchor="We then coded")
    issue = _issue(description="“Data were collected…” and “We then coded the notes.”")
    values, _ = issue_detection_scores([issue], _inventory([f1, f2]))
    assert values["recall"] == 1.0 and values["precision"] == 1.0


def test_recall_precision_and_f05():
    f_hit = _expected(id="hit")
    f_missed = _expected(id="missed", anchor="Findings are listed", line=9)
    issues = [_issue(description="“Data were collected”"), _issue(description="unrelated", start=2, end=2)]
    values, note = issue_detection_scores(issues, _inventory([f_hit, f_missed]))
    assert values["recall"] == 0.5 and values["precision"] == 0.5
    assert values["f0_5"] == pytest.approx(0.5)
    assert "missing missed" in note


def test_clean_document_metric():
    values, _ = issue_detection_scores([], _inventory())
    assert values["clean_document_untouched"] == 1.0
    assert math.isnan(values["recall"]) and math.isnan(values["precision"])
    values, _ = issue_detection_scores([_issue(description="anything")], _inventory())
    assert values["clean_document_untouched"] == 0.0


def test_decoy_hits_by_reason_over_the_dataset_wide_reason_list():
    decoys = [Decoy(anchor="is limited to", reason="stative"), Decoy(anchor="We then coded", reason="active")]
    issue = _issue(description="“The scope is limited to urban sites.”", start=9, end=9)
    assert [d.reason for d in decoy_hits(decoys, [issue])] == ["stative"]
    values, note = decoy_scores([issue], _inventory(decoys=decoys), REASONS)
    assert set(values) == {f"no_fp_{r}" for r in REASONS}
    assert values["no_fp_stative"] == 0.0
    assert values["no_fp_active"] == 1.0
    assert math.isnan(values["no_fp_generic"]), "a reason absent from this sample is unscored, not passed"
    assert "false positive (stative)" in note


def test_title_severity_and_range_metrics_follow_the_hit():
    f = _expected(severity="low")
    wrong = _issue(title="Something Else", description="“Data were collected”", start=1, end=1, severity="medium")
    values, _ = issue_detection_scores([wrong], _inventory([f]))
    assert values["recall"] == 1.0
    assert values["title_correct"] == 0.0 and values["severity_correct"] == 0.0 and values["anchor_in_range"] == 0.0


def test_issue_detection_scores_always_return_the_same_key_set():
    values, _ = issue_detection_scores([], _inventory())
    assert set(values) == set(DETECTION_KEYS) | set(EDIT_KEYS)


def test_extra_edit_scores_are_keyed_by_check_name_and_nan_without_edits():
    f = _expected(edit_expected=True)
    with_edit = _issue(description="“Data were collected”", edits=[_edit("Data were collected from 3 sites by the field team.", "The field team collected data from 3 sites.")])
    values, _ = extra_edit_scores([with_edit], _inventory([f]), {"mentions_team": lambda e: "team" in e.replacement_text})
    assert values == {"edit_mentions_team": 1.0}
    values, _ = extra_edit_scores([_issue(description="“Data were collected”")], _inventory([f]), {"mentions_team": lambda e: True})
    assert math.isnan(values["edit_mentions_team"])


# --- edits ------------------------------------------------------------------------


def test_edit_present_or_absent_as_the_inventory_expects():
    wants = _expected(edit_expected=True)
    forbids = _expected(edit_expected=False)
    bare = _issue(description="“Data were collected”")
    with_edit = _issue(description="“Data were collected”", edits=[_edit("Data were collected from 3 sites by the field team.", "The field team collected data from 3 sites.")])
    assert edit_checks(wants, bare, LINES)["edit_present_when_expected"][0] == 0.0
    assert edit_checks(wants, with_edit, LINES)["edit_present_when_expected"][0] == 1.0
    assert edit_checks(forbids, bare, LINES)["edit_absent_when_not_expected"][0] == 1.0
    assert edit_checks(forbids, with_edit, LINES)["edit_absent_when_not_expected"][0] == 0.0


def test_edits_on_a_shared_line_are_paired_by_text_not_line():
    """Two expected issues in one paragraph each get only the edit that quotes their sentence."""
    f1 = _expected(id="a", anchor="Data were collected", edit_expected=True, edit={"must_include": ["field team collected"]})
    f2 = _expected(id="b", anchor="We then coded", edit_expected=True, edit={"must_include": ["coded"]})
    issue = _issue(
        description="“Data were collected…” and “We then coded the notes.”",
        edits=[
            _edit("Data were collected from 3 sites by the field team.", "The field team collected data from 3 sites."),
            _edit("We then coded the notes.", "We coded the notes next."),
        ],
    )
    assert edit_checks(f1, issue, LINES)["edit_expected_phrases"][0] == 1.0
    assert edit_checks(f2, issue, LINES)["edit_expected_phrases"][0] == 1.0


def test_edit_quote_must_be_on_the_line():
    f = _expected(edit_expected=True)
    good = _issue(edits=[_edit("Data were collected from 3 sites by the field team.", "The field team collected data from 3 sites.")])
    bad = _issue(edits=[_edit("Data were collected from 4 sites.", "x")])
    assert edit_checks(f, good, LINES)["edit_quote_on_line"][0] == 1.0
    assert edit_checks(f, bad, LINES)["edit_quote_on_line"][0] == 0.0


def test_edit_phrases_numbers_and_punctuation():
    f = _expected(edit_expected=True, edit={"must_include": ["field team collected"], "must_not_include": ["The authors"]})
    original = "Data were collected from 3 sites by the field team."
    cases = {
        "edit_keeps_numbers_and_markers": _edit(original, "The field team collected data."),
        "edit_punctuation": _edit(original, "The field team collected data from 3 sites,."),
        "edit_expected_phrases": _edit(original, "The authors collected data from 3 sites."),
    }
    for key, edit in cases.items():
        assert edit_checks(f, _issue(edits=[edit]), LINES)[key][0] == 0.0, key
    clean = edit_checks(f, _issue(edits=[_edit(original, "The field team collected data from 3 sites.")]), LINES)
    assert all(clean[k][0] == 1.0 for k in ("edit_keeps_numbers_and_markers", "edit_punctuation", "edit_expected_phrases"))


def test_footnote_markers_and_citations_count_as_tokens():
    f = _expected(edit_expected=True, anchor="Findings are listed", line=9)
    line = "Findings are listed in Appendix A (Smith, 2024).[[3]](#footnote-4)"
    lines = LINES[:8] + [line]
    keeps = _edit(line, "Appendix A lists findings (Smith, 2024).[[3]](#footnote-4)", line=9)
    drops = _edit(line, "Appendix A lists findings (Smith, 2024).", line=9)
    assert edit_checks(f, _issue(start=9, end=9, edits=[keeps]), lines)["edit_keeps_numbers_and_markers"][0] == 1.0
    assert edit_checks(f, _issue(start=9, end=9, edits=[drops]), lines)["edit_keeps_numbers_and_markers"][0] == 0.0


def test_sentence_final_number_is_not_a_different_token():
    f = _expected(edit_expected=True, anchor="Findings are listed", line=9)
    line = "Findings are listed in Figure 1."
    lines = LINES[:8] + [line]
    moved = _edit(line, "Figure 1 lists findings.", line=9)
    assert edit_checks(f, _issue(start=9, end=9, edits=[moved]), lines)["edit_keeps_numbers_and_markers"][0] == 1.0


def test_comma_stranded_behind_a_moved_footnote_marker_is_caught():
    f = _expected(edit_expected=True, anchor="listed in Appendix A", line=9)
    line = "Findings, listed in Appendix A,[[3]](#footnote-4) were shared."
    lines = LINES[:8] + [line]
    stranded = _edit(line, "We shared findings, listed in Appendix A,[[3]](#footnote-4).", line=9)
    clean = _edit(line, "We shared findings, listed in Appendix A.[[3]](#footnote-4)", line=9)
    assert edit_checks(f, _issue(start=9, end=9, edits=[stranded]), lines)["edit_punctuation"][0] == 0.0
    assert edit_checks(f, _issue(start=9, end=9, edits=[clean]), lines)["edit_punctuation"][0] == 1.0


def test_workflow_specific_edit_checks_are_reported_under_their_name():
    f = _expected(edit_expected=True)
    issue = _issue(edits=[_edit("Data were collected from 3 sites by the field team.", "The field team collected data from 3 sites.")])
    results = edit_checks(f, issue, LINES, {"mentions_team": lambda e: "team" in e.replacement_text})
    assert results["edit_mentions_team"][0] == 1.0
