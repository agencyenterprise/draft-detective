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
    issue_check_keys,
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


def test_extra_check_none_verdicts_are_left_out_of_the_fraction():
    f = _expected(edit_expected=True)
    original = LINES[4].split(". ")[0] + "."
    edits = [_edit(original, "The field team collected data from 3 sites."), _edit(original, "Data were collected from 3 sites by the field team.")]
    verdicts = iter([None, False])
    out = edit_checks(f, _issue(edits=edits), LINES, {"probe": lambda e: next(verdicts)})
    assert out["edit_probe"] == (0.0, "f: 0/1 replacements pass probe (1 not assessable)")

    out = edit_checks(f, _issue(edits=edits[:1]), LINES, {"probe": lambda e: None})
    assert "edit_probe" not in out


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
    values, note = issue_detection_scores([wrong], _inventory([f]))
    assert values["recall"] == 1.0
    assert values["title_correct"] == 0.0 and values["severity_correct"] == 0.0 and values["anchor_in_range"] == 0.0
    # The explanation names the issue behind each mismatch, so a reader need not open the run.
    assert "f: reported as 'Something Else', not under 'Passive Voice'" in note
    assert "f: severity medium, expected low" in note
    assert "f: lines 1-1 do not bracket line 5" in note


def test_title_matches_as_whole_words_anywhere_in_the_reported_title():
    f = _expected(title="Passive Voice")
    assert hit_issue(f, [_issue(title="Passive Voice: Section Summary", description="“Data were collected”")]) == 0
    assert hit_issue(f, [_issue(title="Section summary: passive voice", description="“Data were collected”")]) == 0
    # Quoted under an unrelated title still counts as detected, but under the third tier: title_correct records it.
    values, _ = issue_detection_scores([_issue(title="Wordy Sentence", description="“Data were collected”")], _inventory([f]))
    assert values["recall"] == 1.0 and values["title_correct"] == 0.0

    supported = _expected(title="supported", severity="none")
    quoted = "“Data were collected”"
    values, _ = issue_detection_scores([_issue(title="Unsupported recommendation: x", description=quoted)], _inventory([supported]))
    assert values["title_correct"] == 0.0, "a whole-word match: 'supported' is not inside 'unsupported'"
    values, _ = issue_detection_scores([_issue(title="Recommendation partially supported: x", description=quoted)], _inventory([supported]))
    assert values["title_correct"] == 1.0


def test_an_expected_issue_without_a_title_matches_any_title_by_line_and_is_not_title_scored():
    f = _expected(title=None, severity="high")
    paraphrased = _issue(title="Unsupported recommendation: collect more data", description="No finding backs this.", severity="high")
    assert hit_issue(f, [paraphrased]) == 0
    values, _ = issue_detection_scores([paraphrased], _inventory([f]))
    assert values["recall"] == 1.0 and values["severity_correct"] == 1.0
    assert math.isnan(values["title_correct"]), "no title to hold the run to"


def test_one_to_one_matching_counts_a_merged_occurrence_as_missing():
    first = _expected(id="first", title=None, anchor="Data were collected", line=5)
    second = _expected(id="second", title=None, anchor="Findings are listed", line=9)
    merged = _issue(title="Two in one", description="“Data were collected” and “Findings are listed”", start=5, end=9)

    values, _ = issue_detection_scores([merged], _inventory([first, second]))
    assert values["recall"] == 1.0, "by default one paragraph-level issue may cover several expected issues"

    values, note = issue_detection_scores([merged], _inventory([first, second]), one_to_one=True)
    assert values["recall"] == 0.5 and values["precision"] == 1.0
    assert "missing second" in note and "merged into an issue that already covers another expected issue: second" in note

    separate = [_issue(title="A", description="“Data were collected”"), _issue(title="B", description="“Findings are listed”", start=9, end=9)]
    values, _ = issue_detection_scores(separate, _inventory([first, second]), one_to_one=True)
    assert values["recall"] == 1.0 and values["precision"] == 1.0


def test_one_to_one_matching_finds_a_complete_pairing_regardless_of_order():
    # The broad issue quotes A and B; the narrow one quotes only A. Greedy matching in
    # inventory order would give A the broad issue and leave B missing.
    a = _expected(id="a", title=None, anchor="Data were collected", line=5)
    b = _expected(id="b", title=None, anchor="Findings are listed", line=9)
    broad = _issue(title="Both", description="“Data were collected” “Findings are listed”", start=5, end=9)
    narrow = _issue(title="A only", description="“Data were collected”")

    values, _ = issue_detection_scores([broad, narrow], _inventory([a, b]), one_to_one=True)
    assert values["recall"] == 1.0 and values["precision"] == 1.0


@pytest.mark.parametrize("reversed_order", [False, True])
def test_one_to_one_matching_keeps_the_strongest_evidence_whatever_the_output_order(reversed_order):
    # Both issues bracket both recommendations; only the first quotes its anchor. The pairing
    # that keeps the quote is the right one, and it must not depend on which issue came first.
    a = _expected(id="a", title=None, anchor="Data were collected", line=5, severity="low")
    b = _expected(id="b", title=None, anchor="Findings are listed", line=9, severity="high")
    quotes_a = _issue(title="A", description="“Data were collected” by the team", start=5, end=9, severity="low")
    paraphrases_b = _issue(title="B", description="The appendix listing is passive.", start=5, end=9, severity="high")
    issues = [paraphrases_b, quotes_a] if reversed_order else [quotes_a, paraphrases_b]

    values, _ = issue_detection_scores(issues, _inventory([a, b]), one_to_one=True)

    assert values["recall"] == 1.0 and values["severity_correct"] == 1.0


@pytest.mark.parametrize("one_to_one", [False, True])
@pytest.mark.parametrize("reversed_order", [False, True])
def test_line_range_breaks_a_tie_between_issues_that_quote_both_occurrences(one_to_one, reversed_order):
    # A recommendation and its restatement, each reported by an issue that quotes both wordings
    # (to say it is a restatement) but brackets only its own line. The range must decide.
    summary = _expected(id="summary", title=None, anchor="Data were collected", line=5, severity="none")
    detailed = _expected(id="detailed", title=None, anchor="Findings are listed", line=9, severity="medium")
    both = "“Data were collected” restates “Findings are listed”"
    on_summary = _issue(title="Supported: summary", description=both, start=5, end=5, severity="none")
    on_detailed = _issue(title="Partially supported: detailed", description=both, start=9, end=9, severity="medium")
    issues = [on_detailed, on_summary] if reversed_order else [on_summary, on_detailed]

    values, _ = issue_detection_scores(issues, _inventory([summary, detailed]), one_to_one=one_to_one)

    assert values["recall"] == 1.0 and values["severity_correct"] == 1.0 and values["anchor_in_range"] == 1.0


@pytest.mark.parametrize("optional_first", [False, True])
def test_one_to_one_matching_gives_a_shared_report_to_the_required_expectation(optional_first):
    required = _expected(id="required", title=None, anchor="Data were collected", line=5, required=True)
    optional = _expected(id="optional", title=None, anchor="We then coded", line=5, required=False)
    shared = _issue(title="One report", description="“Data were collected” and “We then coded”")
    expected = [optional, required] if optional_first else [required, optional]

    values, note = issue_detection_scores([shared], _inventory(expected), one_to_one=True)

    assert values["recall"] == 1.0, "the optional expectation must not consume the report the required one needs"
    assert "missing" not in note


@pytest.mark.parametrize("one_to_one", [False, True])
def test_evidence_tied_reports_are_matched_the_same_way_in_either_order(one_to_one):
    # The saved case: one recommendation reported as two issues on its line, neither quoting
    # it, one medium and one supported. Evidence cannot tell them apart, so the pairing must at
    # least not depend on which the workflow listed first.
    expected = _expected(id="near_miss", title=None, anchor="Data were collected", line=5, severity="none")
    partial = _issue(title="Partially supported recommendation: continue encouraging", description="Direction only.", severity="medium")
    supported = _issue(title="Supported recommendation: treat increases as positive", description="Directly grounded.", severity="none")

    forward, _ = issue_detection_scores([partial, supported], _inventory([expected]), one_to_one=one_to_one)
    backward, _ = issue_detection_scores([supported, partial], _inventory([expected]), one_to_one=one_to_one)

    assert forward == backward
    assert forward["recall"] == 1.0
    if one_to_one:
        assert forward["precision"] == 0.5, "the split itself is charged to precision, whichever half is paired"


def test_canonical_order_is_total_over_report_content():
    from evals_inspectai.common.issue_checks import _canonical_order

    a = _issue(title="Same title", description="Same text.", severity="high", start=5, end=5)
    b = _issue(title="Same title", description="Same text.", severity="none", start=5, end=5)
    earlier = _issue(title="Zed", description="Other.", severity="none", start=3, end=3)
    assert _canonical_order([a, b, earlier]) == [2, 0, 1], "line range first, then text, then severity"
    assert _canonical_order([b, a, earlier]) == [2, 1, 0], "the same reports in another order sort the same"


@pytest.mark.parametrize("one_to_one", [False, True])
def test_reports_differing_only_in_severity_are_matched_the_same_way_in_either_order(one_to_one):
    expected = _expected(id="e", title=None, anchor="Data were collected", line=5, severity="none")
    high = _issue(title="Same title", description="Same text.", severity="high")
    none = _issue(title="Same title", description="Same text.", severity="none")

    forward, _ = issue_detection_scores([high, none], _inventory([expected]), one_to_one=one_to_one)
    backward, _ = issue_detection_scores([none, high], _inventory([expected]), one_to_one=one_to_one)

    assert forward == backward
    assert forward["severity_correct"] in (0.0, 1.0)


def test_repeated_expected_ids_are_rejected_at_load():
    record = InventoryRecord(
        input=DOC,
        expected_issues=[
            {"title": "Passive Voice", "anchor": "Data were collected", "line": 5},
            {"title": "Passive Voice", "anchor": "Data were collected", "line": 5},
        ],
    )
    with pytest.raises(ValueError, match="ids must be unique"):
        resolve_record(record)


def test_title_key_is_left_out_when_the_inventory_names_no_titles():
    assert "title_correct" not in issue_check_keys(edits=False, titles=False)
    assert "title_correct" in issue_check_keys(edits=False, titles=True)
    f = _expected(title=None)
    values, _ = issue_detection_scores([_issue(description="“Data were collected”")], _inventory([f]), edits=False, titles=False)
    assert "title_correct" not in values and values["recall"] == 1.0


def test_edit_keys_are_left_out_for_a_workflow_that_proposes_no_edits():
    values, _ = issue_detection_scores([_issue(description="“Data were collected”")], _inventory([_expected()]), edits=False)
    assert set(values) == set(DETECTION_KEYS)
    assert values["recall"] == 1.0


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


def test_expected_phrases_are_read_off_the_line_with_a_word_level_edit_applied():
    f = _expected(edit_expected=True, edit={"must_include": ["The team collected data"], "must_not_include": ["were collected"]})
    swap = _edit("Data were collected", "The team collected data")  # replaces only the clause, not the sentence
    out = edit_checks(f, _issue(edits=[swap]), LINES)
    assert out["edit_expected_phrases"][0] == 1.0
    wrong = _edit("Data were collected", "Data were gathered")
    assert edit_checks(f, _issue(edits=[wrong]), LINES)["edit_expected_phrases"][0] == 0.0


def test_expected_phrases_are_judged_on_the_edited_sentence_not_its_neighbours():
    lines = ["Respondents rated scheduling. Participants rated scheduling."]
    f = ResolvedIssue(id="f", title=None, anchor="Respondents rated scheduling", line=1, edit_expected=True,
                      edit={"must_include": ["Participants rated scheduling"]})
    # The edit touches the first sentence only; the phrase lives untouched in the second.
    untouched_neighbour = _edit("Respondents rated scheduling.", "Respondents rated the schedule.", line=1)
    assert edit_checks(f, _issue(start=1, end=1, edits=[untouched_neighbour]), lines)["edit_expected_phrases"][0] == 0.0
    # The same phrase produced by a word-level edit in the first sentence passes.
    fixes_it = _edit("Respondents", "Participants", line=1)
    assert edit_checks(f, _issue(start=1, end=1, edits=[fixes_it]), lines)["edit_expected_phrases"][0] == 1.0


def test_forbidden_phrases_left_standing_in_the_edited_sentence_fail():
    f = _expected(edit_expected=True, edit={"must_not_include": ["by the field team"]})
    # A word-level edit whose replacement is clean, but the sentence it produces still carries the phrase.
    partial = _edit("Data were collected", "The team collected data")
    assert edit_checks(f, _issue(edits=[partial]), LINES)["edit_expected_phrases"][0] == 0.0
    whole = _edit("Data were collected from 3 sites by the field team.", "The field team collected data from 3 sites.")
    assert edit_checks(f, _issue(edits=[whole]), LINES)["edit_expected_phrases"][0] == 1.0


def test_percentage_units_travel_with_their_number():
    line = "Retention rose 7% in the same period."
    lines = LINES[:8] + [line]
    f = _expected(anchor="Retention rose 7% in the same period", line=9)
    keeps_unit = _edit("Retention rose 7% in the same period.", "Retention rose 7 percent in the same period.", line=9)
    drops_unit = _edit("Retention rose 7% in the same period.", "Retention rose 7 in the same period.", line=9)
    british = _edit("Retention rose 7% in the same period.", "Retention rose 7 per cent in the same period.", line=9)
    check = lambda e: edit_checks(f, _issue(start=9, end=9, edits=[e]), lines)["edit_keeps_numbers_and_markers"][0]
    assert check(keeps_unit) == 1.0 and check(british) == 1.0
    assert check(drops_unit) == 0.0, "a bare 7 is not 7 percent"


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
