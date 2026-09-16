"""Proposed edits must survive the trip from tool call to persisted row.

Covers the two pure steps between them: the agent-result to DocumentIssue
conversion, and the `IssueEdit` rows the persistence service builds from it.
"""

from lib.models.issue_edit import IssueEditStatus
from lib.services.issue_persistence import _edit_rows
from lib.workflows.models import DocumentIssue, ProposedEdit, WorkflowRunType
from lib.workflows.simple_deep_agent.agent_types import (
    DeepAgentResult,
    IssueItem,
    issues_from_agent_result,
)


def _edit(**overrides) -> ProposedEdit:
    fields: dict = {
        "original_text": "Figure 3",
        "replacement_text": "Figure 2",
        "start_line": 6,
        "end_line": 6,
        "rationale": "Matches the caption.",
    }
    return ProposedEdit(**{**fields, **overrides})


def _issue_item(edits: list[ProposedEdit]) -> IssueItem:
    return IssueItem(
        title="Numbering mismatch",
        description="The body text cites Figure 3 but the caption reads Figure 2.",
        severity="medium",
        start_line=6,
        end_line=6,
        edits=edits,
    )


def test_agent_result_edits_reach_the_document_issue():
    result = DeepAgentResult(issues=[_issue_item([_edit()])], report_markdown="ok")

    (issue,) = issues_from_agent_result(result, WorkflowRunType.FIGURES_TABLES_CHECK)

    (edit,) = issue.edits
    assert edit.original_text == "Figure 3"
    assert edit.replacement_text == "Figure 2"
    assert (edit.start_line, edit.end_line) == (6, 6)


def test_an_issue_without_edits_converts_to_an_empty_list():
    result = DeepAgentResult(issues=[_issue_item([])], report_markdown="ok")

    (issue,) = issues_from_agent_result(result, WorkflowRunType.FIGURES_TABLES_CHECK)

    assert issue.edits == []


def test_edits_are_outside_the_issue_hash():
    """The hash identifies the finding, so attaching a fix must not remint it."""
    fields = {
        "title": "Numbering mismatch",
        "description": "The body text cites Figure 3.",
        "severity": "medium",
        "type": WorkflowRunType.FIGURES_TABLES_CHECK,
        "start_line": 6,
        "end_line": 6,
    }

    assert DocumentIssue(**fields).id == DocumentIssue(**fields, edits=[_edit()]).id


def test_edit_rows_keep_every_field_and_strip_control_chars():
    # PDF-extracted markdown can carry C0 control characters, which PostgreSQL
    # rejects in a text column.
    (row,) = _edit_rows([_edit(original_text="Figure\x003")])

    assert row.original_text == "Figure3"
    assert row.replacement_text == "Figure 2"
    assert row.rationale == "Matches the caption."
    assert row.start_line == 6
    assert row.end_line == 6
    assert row.position == 0
    assert row.status == IssueEditStatus.PROPOSED
    assert row.reviewed_by is None and row.reviewed_at is None


def test_edit_rows_are_numbered_by_the_order_they_were_proposed():
    rows = _edit_rows(
        [_edit(replacement_text="Figure 2"), _edit(replacement_text="Figure 1")]
    )

    assert [(r.position, r.replacement_text) for r in rows] == [
        (0, "Figure 2"),
        (1, "Figure 1"),
    ]


def test_no_edits_builds_no_rows():
    assert _edit_rows([]) == []
