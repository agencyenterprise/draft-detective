"""Unit tests for the passage an issue can quote, through the reporting tool."""

import pytest

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.agent_types import (
    DeepAgentResult,
    issues_from_agent_result,
)
from lib.workflows.simple_deep_agent.issue_reporting import IssueReporter

# Line 3 carries a phrase in bold and a non-breaking space; line 5 repeats
# "must" twice; line 7 is a link whose address a passage cannot start inside.
_DOCUMENT = "\n".join(
    [
        "# Title",  # 1
        "",  # 2
        "The results **certainly** prove\xa0the claim.",  # 3
        "",  # 4
        "We must act, and we must act now.",  # 5
        "",  # 6
        "See [the report](https://x/report_final.pdf) for details.",  # 7
    ]
)


def _report(passage: str | None, propose_edits: bool = False, **overrides) -> tuple:
    reporter = IssueReporter(propose_edits=propose_edits, document_text=_DOCUMENT)
    (report_issue,) = reporter.tools
    arguments = {
        "title": "Trigger word",
        "description": "Certainty language without evidence.",
        "severity": "medium",
        "start_line": 1,
        "end_line": 7,
        "passage": passage,
        **overrides,
    }
    return reporter, report_issue.invoke(arguments)


@pytest.mark.parametrize("propose_edits", [False, True])
def test_a_passage_is_located_and_rendered_on_its_own_line(propose_edits: bool):
    reporter, confirmation = _report(
        "results **certainly** prove the claim", propose_edits
    )

    assert confirmation.startswith("Recorded issue-1")
    passage = reporter.issues[0].passage
    assert passage is not None
    assert (passage.start_line, passage.end_line) == (3, 3)
    # What the reader sees: no stars, ordinary spacing.
    assert passage.display_text == "results certainly prove the claim"
    assert passage.display_occurrence == 0
    assert passage.original_text == "results **certainly** prove the claim"


@pytest.mark.parametrize("passage", [None, "", "   "])
def test_an_issue_without_a_passage_is_recorded_as_a_whole_line_issue(
    passage: str | None,
):
    reporter, confirmation = _report(passage)

    assert confirmation.startswith("Recorded issue-1")
    assert reporter.issues[0].passage is None


def test_a_passage_missing_from_the_lines_is_rejected_with_the_way_out():
    reporter, rejection = _report("this sentence is not there")

    assert rejection.startswith("Issue was not recorded: passage was not found")
    assert "Lines 1-7 read" in rejection
    assert "If the issue concerns more than one line, omit passage." in rejection
    assert reporter.issues == []


def test_a_passage_crossing_a_line_break_is_rejected():
    _, rejection = _report("Title The results", start_line=1, end_line=3)

    assert "passage was not found on any single line" in rejection


def test_a_repeated_passage_is_rejected_until_it_is_unique():
    reporter, rejection = _report("must act")

    assert "passage appears 2 times in lines 1-7" in rejection
    assert "omit passage if the issue concerns the whole line" in rejection

    _, confirmation = _report("we must act now")
    assert confirmation.startswith("Recorded")


def test_a_passage_outside_the_issue_range_is_rejected():
    _, rejection = _report("We must act, and we must act now.", end_line=3)

    assert "passage was not found" in rejection


def test_a_passage_starting_inside_a_link_address_is_rejected():
    _, rejection = _report("report_final.pdf) for details")

    assert "passage must start and end on plain text" in rejection


def test_display_math_is_refused_as_a_passage():
    _, rejection = _report("$$x$$")

    assert "passage must not contain display math" in rejection


def test_a_reporter_without_the_document_cannot_check_a_passage():
    reporter = IssueReporter()
    (report_issue,) = reporter.tools

    rejection = report_issue.invoke(
        {
            "title": "Trigger word",
            "description": "Certainty language.",
            "severity": "low",
            "start_line": 1,
            "end_line": 1,
            "passage": "anything",
        }
    )

    assert rejection == (
        "Issue was not recorded: passage cannot be checked here; omit it."
    )


def test_the_same_finding_with_and_without_a_passage_is_a_duplicate():
    reporter, _ = _report("results **certainly** prove the claim")
    (report_issue,) = reporter.tools

    duplicate = report_issue.invoke(
        {
            "title": "Trigger word",
            "description": "Certainty language without evidence.",
            "severity": "medium",
            "start_line": 1,
            "end_line": 7,
        }
    )

    assert "duplicate ignored" in duplicate
    assert len(reporter.issues) == 1


@pytest.mark.parametrize("propose_edits", [False, True])
def test_both_tool_variants_offer_an_optional_passage(propose_edits: bool):
    reporter = IssueReporter(propose_edits=propose_edits, document_text=_DOCUMENT)
    (report_issue,) = reporter.tools
    schema = report_issue.args_schema.model_json_schema()  # type: ignore[union-attr]

    assert "passage" in schema["properties"]
    assert "passage" not in schema.get("required", [])
    assert "omit it when the issue concerns the whole line" in (
        report_issue.description
    )


def test_the_passage_reaches_the_document_issue():
    reporter, _ = _report("results **certainly** prove the claim")

    (issue,) = issues_from_agent_result(
        DeepAgentResult(issues=reporter.issues), WorkflowRunType.ACTIVE_VOICE
    )

    assert issue.passage == reporter.issues[0].passage
