"""The Headers & Skimmability eval: its dataset, task and the checks on suggested wording."""

import math
from pathlib import Path

from evals_inspectai.common.issue_checks import decoy_hits
from evals_inspectai.common.issue_inventory import (
    Decoy,
    ResolvedInventory,
    ResolvedIssue,
    decoy_reasons,
    expects_edits,
    load_inventory_records,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.headers_skimmability.criteria import (
    JUDGE_CRITERIA,
    header_words,
    section_number,
    suggestion,
    suggestion_scores,
)
from evals_inspectai.e2e.headers_skimmability.headers_skimmability_e2e import headers_skimmability_e2e

DATASET = Path("evals_inspectai/e2e/headers_skimmability/dataset.yaml")
DOC = "# Report\n\n## 3. Results\n\nScores rose.\n\n**Crews.** Crews fixed leaks in 9 days.\n"


def _inventory(*expected: ResolvedIssue) -> ResolvedInventory:
    return ResolvedInventory(document=DOC, expected_issues=list(expected), decoys=[])


HEADER = ResolvedIssue(id="results", title="Vague Header", anchor="3. Results", line=3)
LEAD = ResolvedIssue(id="crews", title="Lead Sentence Lacks Takeaway", anchor="**Crews.**", line=7)


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 16
    assert sum(1 for r in records if not r.expected_issues) == 7, "seven clean documents"
    titles = {e.title for r in records for e in r.expected_issues}
    assert titles == {
        "Header",
        "Vague Header",
        "Header Lacks Takeaway",
        "Header Does Not Match Content",
        "Bottom Line Not Up Front",
        "Lead Sentence Lacks Takeaway",
        "Too Many Key Findings",
        "Key Finding Not Brief",
    }
    assert set(decoy_reasons(records)) == {
        "alternative_header",
        "argued_lead",
        "bold_emphasis",
        "document_title",
        "named_section",
        "procedural_header",
        "procedural_lead",
        "protected_header",
        "signposting",
    }
    assert expects_edits(records) is False


def test_suggestion_is_read_from_its_fixed_form():
    assert suggestion('Suggested header: "3. Scores Rose" This says what was found.', "header") == "3. Scores Rose"
    assert suggestion("Suggested lead: “Crews Fixed Leaks Faster.”", "lead") == "Crews Fixed Leaks Faster."
    assert suggestion('Suggested lead: "Crews Fixed Leaks Faster."', "header") is None
    assert suggestion("Retitle the section to say what it found.", "header") is None
    assert suggestion(None, "header") is None
    # Markdown marks around the wording are not part of it.
    assert suggestion('Suggested header: "## 3. Voucher Users Had Higher Employment"', "header") == "3. Voucher Users Had Higher Employment"
    assert suggestion('Suggested lead: "**Moves Were Mostly Local.**"', "lead") == "Moves Were Mostly Local."
    # A quotation inside the wording does not end it.
    nested = 'Suggested header: "Staff Called Tutoring \"Unsustainable\" Without Funding" This says why.'
    assert suggestion(nested, "header") == 'Staff Called Tutoring "Unsustainable" Without Funding'
    assert suggestion("Suggested header: “Staff Called It “Unsustainable”” ok", "header") == "Staff Called It “Unsustainable”"


def test_section_numbers_and_header_length():
    assert section_number("3. Results") == "3"
    assert section_number("2.1 Background") == "2.1"
    assert section_number("Chapter 4: Discussion") == "chapter 4"
    assert section_number("Findings") is None
    assert header_words("Chapter 3: Losses Fell but Gaps Persist") == 5
    assert header_words("3. Results") == 1
    assert section_number("Part II: Costs") == "part ii"
    # A word after "Part" and a leading year or count are not section numbers.
    assert section_number("Part of the Gain Faded by Year Two") is None
    assert header_words("Part of the Gain Faded by Year Two") == 8
    assert section_number("2024 Rate Increase") is None
    assert header_words("40 Percent of Crews Missed Targets") == 6


def test_suggestion_scores_check_form_length_and_number():
    good = IssueItem(title="Vague Header", start_line=3, end_line=3, suggested_action='Suggested header: "3. Voucher Users Had Higher Employment"')
    lead = IssueItem(title="Lead Sentence Lacks Takeaway", start_line=7, end_line=7, suggested_action='Suggested lead: "Crews Fixed Leaks Faster."')
    values, _ = suggestion_scores([good, lead], _inventory(HEADER, LEAD))
    assert values == {"suggestion_in_form": 1.0, "suggestion_header_length": 1.0, "suggestion_keeps_number": 1.0}

    dropped = IssueItem(title="Vague Header", start_line=3, end_line=3, suggested_action='Suggested header: "Voucher Users Had Higher Employment Rates Than Eligible Nonusers Overall"')
    values, explanation = suggestion_scores([dropped], _inventory(HEADER))
    assert values["suggestion_header_length"] == 0.0 and values["suggestion_keeps_number"] == 0.0
    assert "drops the number" in explanation

    unformed = IssueItem(title="Lead Sentence Lacks Takeaway", start_line=7, end_line=7, suggested_action="State the point.")
    values, _ = suggestion_scores([unformed], _inventory(LEAD))
    assert values["suggestion_in_form"] == 0.0
    assert math.isnan(values["suggestion_header_length"]) and math.isnan(values["suggestion_keeps_number"])


def test_an_optional_header_issue_titled_header_gets_the_suggestion_checks():
    optional = ResolvedIssue(id="results", title="Header", anchor="3. Results", line=3, required=False)
    long = IssueItem(title="Header Lacks Takeaway", start_line=3, end_line=3, suggested_action='Suggested header: "Scores Rose in Every Grade and Every School in the District"')
    values, explanation = suggestion_scores([long], _inventory(optional))
    assert values == {"suggestion_in_form": 1.0, "suggestion_header_length": 0.0, "suggestion_keeps_number": 0.0}
    assert all(c.applies_to is not None and c.applies_to(optional) for c in JUDGE_CRITERIA)


def test_a_one_word_header_decoy_needs_a_header_issue_on_its_line():
    doc = "# Report\n\n## Introduction\n\nWe found X.\n\n## Chapter 2: Data\n\nRecords.\n"
    decoy = Decoy(anchor="## Introduction", reason="named_section", title="Header")
    elsewhere = IssueItem(title="Header Lacks Takeaway", description="Unlike the introduction, this header names no finding.", start_line=7, end_line=7)
    on_it = IssueItem(title="Vague Header", description="'Introduction' is generic.", start_line=3, end_line=3)
    assert decoy_hits([decoy], [elsewhere], doc.split("\n")) == []
    assert decoy_hits([decoy], [on_it], doc.split("\n")) == [decoy]


def test_task_composes_the_inventory_scorers_and_its_own_checks():
    t = headers_skimmability_e2e()
    assert len(t.dataset) == 16 and len(t.scorer) == 4
    assert {c.key for c in JUDGE_CRITERIA} == {"suggestion_supported", "suggestion_states_point"}
    assert all(c.passage == "section" for c in JUDGE_CRITERIA)
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__suggestion_checks__suggestion_in_form" in columns
    assert not any("edit_" in c for c in columns), "no edit keys for a workflow that proposes no edits"
