"""Unit tests for the per-invocation issue-reporting tools."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from langchain_core.messages import AIMessage, ToolMessage

from lib.workflows.simple_deep_agent.issue_reporting import (
    IssueReporter,
    collect_deep_agent_run,
)


def _tools(reporter: IssueReporter) -> dict:
    return {tool.name: tool for tool in reporter.tools}


def _issue(title: str = "Missing section") -> dict:
    return {
        "title": title,
        "description": "The required section was not found.",
        "severity": "high",
        "start_line": 1,
        "end_line": 1,
        "suggested_action": "Add the required section.",
    }


# Line 4 carries a non-breaking space, as converted DOCX prose often does; line
# 6 repeats "Figure 3" twice, so a quote of it is ambiguous. Line 8 carries the
# same phrase plain and in bold, so only the rendered form tells them apart,
# and a link whose label an edit can quote but whose address it cannot. Line 10
# carries a bold run an edit can quote half of, and a parenthetical whose
# closing bracket a replacement can fall foul of.
_DOCUMENT = "\n".join(
    [
        "# Title",  # 1
        "",  # 2
        "The CBT protocol was applied to every",  # 3
        "participant in the second\xa0cohort.",  # 4
        "",  # 5
        "Results appear in Figure 3 and Figure 3.",  # 6
        "",  # 7
        "Figure 3 and **Figure 3** close [the study](https://x/a_b).",  # 8
        "",  # 9
        "The **old phrase** matters to the cohort (n = 40).",  # 10
    ]
)


def _issue_with_edits(edits: list[dict], **overrides) -> dict:
    """An issue over the whole sample document, carrying proposed edits."""
    return {
        **_issue("Numbering mismatch"),
        "start_line": 1,
        "end_line": 10,
        "edits": edits,
        **overrides,
    }


def test_report_issue_collects_a_typed_issue():
    reporter = IssueReporter()
    tools = _tools(reporter)

    confirmation = tools["report_issue"].invoke(_issue())

    assert confirmation.startswith("Recorded issue-1")
    assert [issue.title for issue in reporter.issues] == ["Missing section"]


def test_tool_description_is_document_path_agnostic():
    description = _tools(IssueReporter())["report_issue"].description
    assert "document under review" in description
    assert "/main.md" not in description


def test_invalid_line_ranges_and_blank_fields_are_not_recorded():
    reporter = IssueReporter()
    report_issue = _tools(reporter)["report_issue"]

    for overrides in (
        {"title": ""},
        {"description": "  "},
        {"start_line": 0},
        {"start_line": 5, "end_line": 4},
    ):
        result = report_issue.invoke({**_issue(), **overrides})
        assert result.startswith("Issue was not recorded:")

    assert reporter.issues == []


def test_exact_duplicate_calls_are_suppressed():
    reporter = IssueReporter()
    report_issue = _tools(reporter)["report_issue"]

    assert report_issue.invoke(_issue()).startswith("Recorded issue-1")
    assert "duplicate ignored" in report_issue.invoke(_issue())
    assert len(reporter.issues) == 1


def test_collectors_are_isolated_and_safe_for_parallel_calls():
    first = IssueReporter()
    second = IssueReporter()
    first_tool = _tools(first)["report_issue"]
    second_tool = _tools(second)["report_issue"]

    calls = [(first_tool, _issue(f"First {index}")) for index in range(10)] + [
        (second_tool, _issue(f"Second {index}")) for index in range(10)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda call: call[0].invoke(call[1]), calls))

    assert {issue.title for issue in first.issues} == {
        f"First {index}" for index in range(10)
    }
    assert {issue.title for issue in second.issues} == {
        f"Second {index}" for index in range(10)
    }


def test_collected_run_does_not_carry_viewed_image_bytes():
    """Run messages are persisted as the workflow's state_json and served with
    the run detail, so a viewed image must be reduced to a note there."""
    image_result = ToolMessage(
        content=[{"type": "image", "data": "QUJDRA==", "mime_type": "image/png"}],
        tool_call_id="call-1",
        name="view_image",
    )
    run = collect_deep_agent_run(
        {"files": {}, "messages": [AIMessage(content="done"), image_result]}
    )

    assert "QUJDRA==" not in str(run.messages)
    assert "image/png" in str(run.messages[1].content)


def test_edit_is_accepted_and_narrowed_to_the_line_it_sits_on():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    confirmation = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "participant in the second cohort",
                    "replacement_text": "participant in the second group",
                    "rationale": "Matches the wording used elsewhere.",
                }
            ]
        )
    )

    assert confirmation.startswith("Recorded issue-1")
    (edit,) = reporter.issues[0].edits
    # The quote is anchored to its own line -- not the whole 1-6 range the issue
    # was reported against -- and matched despite the document's non-breaking
    # space.
    assert (edit.start_line, edit.end_line) == (4, 4)
    assert edit.rationale == "Matches the wording used elsewhere."


def test_every_edit_is_kept_in_the_order_it_was_proposed():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "# Title",
                    "replacement_text": "# Report",
                    "rationale": "r",
                },
                {
                    "original_text": "second cohort.",
                    "replacement_text": "second cohort (n = 40).",
                    "rationale": "r",
                },
            ]
        )
    )

    edits = reporter.issues[0].edits
    assert [e.replacement_text for e in edits] == [
        "# Report",
        "second cohort (n = 40).",
    ]
    assert [(e.start_line, e.end_line) for e in edits] == [(1, 1), (4, 4)]


def test_edit_whose_quote_is_absent_is_rejected_with_an_excerpt():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    result = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "the third cohort",
                    "replacement_text": "the cohort",
                    "rationale": "r",
                }
            ],
            start_line=3,
            end_line=4,
        )
    )

    assert result.startswith("Issue was not recorded:")
    assert "was not found on any single line of lines 3-4" in result
    # The range is quoted back so the agent can re-quote from it.
    assert "participant in the second cohort." in result
    assert reporter.issues == []


def test_ambiguous_quote_is_rejected_until_a_unique_span_is_quoted():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    rejected = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "Figure 3",
                    "replacement_text": "Figure 2",
                    "rationale": "r",
                }
            ]
        )
    )
    assert rejected.startswith("Issue was not recorded:")
    assert "appears 4 times" in rejected
    assert "longer span" in rejected

    # The whole line is always unique on itself, so the agent can widen the
    # quote and make the replacement inside it.
    accepted = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "Results appear in Figure 3 and Figure 3.",
                    "replacement_text": "Results appear in Figure 3 and Figure 2.",
                    "rationale": "r",
                }
            ]
        )
    )
    assert accepted.startswith("Recorded issue-1")
    (edit,) = reporter.issues[0].edits
    assert (edit.start_line, edit.end_line) == (6, 6)


def test_quote_across_a_line_break_is_rejected():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    result = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "applied to every participant",
                    "replacement_text": "applied to each participant",
                    "rationale": "r",
                }
            ]
        )
    )

    assert result.startswith("Issue was not recorded:")
    assert "not found on any single line" in result
    assert reporter.issues == []


def test_blank_or_unchanged_replacements_are_rejected():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    identical = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "# Title",
                    "replacement_text": "# Title",
                    "rationale": "r",
                }
            ]
        )
    )
    assert "identical to original_text" in identical

    blank = report_issue.invoke(
        _issue_with_edits(
            [{"original_text": "   ", "replacement_text": "# Report", "rationale": "r"}]
        )
    )
    assert "original_text must not be blank" in blank

    assert reporter.issues == []


def test_deletion_is_expressed_as_an_empty_replacement():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    confirmation = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": " and Figure 3",
                    "replacement_text": "",
                    "rationale": "r",
                }
            ]
        )
    )

    assert confirmation.startswith("Recorded issue-1")
    (edit,) = reporter.issues[0].edits
    assert edit.replacement_text == ""
    # An empty replacement renders to an empty one: that is the deletion
    # contract the export and the highlight both read.
    assert edit.display_replacement == ""


def test_a_recorded_edit_carries_the_text_the_document_renders():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "**Figure 3**",
                    "replacement_text": "**Figure 4**",
                    "rationale": "r",
                }
            ]
        )
    )

    (edit,) = reporter.issues[0].edits
    # The quote is unique in the markdown and the second of two identical spans
    # once the page shows it, which is exactly what the highlight and the
    # export need to be told.
    assert edit.display_text == "Figure 3"
    assert edit.display_occurrence == 1
    assert edit.display_replacement == "Figure 4"


def test_a_quote_whose_text_is_plain_renders_to_itself():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "participant in the second cohort",
                    "replacement_text": "participant in the second group",
                    "rationale": "r",
                }
            ]
        )
    )

    (edit,) = reporter.issues[0].edits
    assert edit.display_text == "participant in the second cohort"
    assert edit.display_occurrence == 0
    assert edit.display_replacement == "participant in the second group"


def test_a_whole_heading_replacement_drops_the_block_syntax():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "# Title",
                    "replacement_text": "# Report",
                    "rationale": "r",
                }
            ]
        )
    )

    (edit,) = reporter.issues[0].edits
    # The quote opened its line, so it took the hashes with it and the
    # replacement was written carrying them. Word shows neither.
    assert edit.display_text == "Title"
    assert edit.display_replacement == "Report"


def test_a_mid_line_replacement_keeps_a_hash_that_is_not_block_syntax():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "second cohort.",
                    "replacement_text": "cohort # 2.",
                    "rationale": "r",
                }
            ]
        )
    )

    (edit,) = reporter.issues[0].edits
    assert edit.display_replacement == "cohort # 2."


def test_a_replacement_closing_the_formatting_its_quote_opened_renders_in_context():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "old phrase**",
                    "replacement_text": "new phrase**",
                    "rationale": "r",
                }
            ]
        )
    )

    (edit,) = reporter.issues[0].edits
    # The quote's trailing stars are the closing half of the document's bold
    # run, and so are the replacement's. Rendered on its own the replacement
    # would keep them as literals and Word would show `new phrase**`.
    assert edit.display_text == "old phrase"
    assert edit.display_replacement == "new phrase"


def test_a_replacement_that_breaks_the_surrounding_formatting_is_rejected():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    # The quote is the parenthetical's contents, so the line's own `)` closes
    # the link destination the replacement opens: nothing of the replacement
    # would reach the page as text.
    result = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "n = 40",
                    "replacement_text": "[forty](https://x",
                    "rationale": "r",
                }
            ]
        )
    )

    assert result.startswith("Issue was not recorded:")
    assert "cannot be placed where original_text sits" in result
    assert "quote the whole formatted span instead" in result
    assert reporter.issues == []


def test_a_quote_ending_inside_a_link_address_is_rejected():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    result = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "close [the study](https://x/a",
                    "replacement_text": "close [the paper](https://x/a",
                    "rationale": "r",
                }
            ]
        )
    )

    assert result.startswith("Issue was not recorded:")
    assert "must start and end on plain text" in result
    assert reporter.issues == []


def test_display_math_is_rejected_in_either_text():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    quoted = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "cohort $$x = 1$$ here",
                    "replacement_text": "cohort here",
                    "rationale": "r",
                }
            ]
        )
    )
    replaced = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "# Title",
                    "replacement_text": "# Title $$x = 1$$",
                    "rationale": "r",
                }
            ]
        )
    )

    for result in (quoted, replaced):
        assert result.startswith("Issue was not recorded:")
        assert "must not contain display math" in result
    assert reporter.issues == []


def test_a_single_dollar_is_money_not_math():
    # The app reads `$...$` as prose (`singleDollarTextMath: false`), so a
    # figure in dollars is an ordinary edit.
    reporter = IssueReporter(
        propose_edits=True, document_text="The grant was $5 million in 2019."
    )
    report_issue = _tools(reporter)["report_issue"]

    confirmation = report_issue.invoke(
        {
            **_issue("Wrong figure"),
            "edits": [
                {
                    "original_text": "$5 million",
                    "replacement_text": "$6 million",
                    "rationale": "r",
                }
            ],
        }
    )

    assert confirmation.startswith("Recorded issue-1")
    assert reporter.issues[0].edits[0].display_replacement == "$6 million"


def test_plain_tool_has_no_edits_argument():
    # Edits are opt-in per workflow: a collector without them hands the agent a
    # tool whose schema and description never mention edits, so the option
    # costs no context where it is not used.
    report_issue = _tools(IssueReporter())["report_issue"]
    schema = report_issue.args_schema.model_json_schema()

    assert "edits" not in schema["properties"]
    assert "ProposedEditInput" not in schema.get("$defs", {})
    assert "edit" not in report_issue.description.lower()


def test_plain_tool_ignores_an_edits_argument_it_did_not_advertise():
    reporter = IssueReporter()
    report_issue = _tools(reporter)["report_issue"]

    result = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "# Title",
                    "replacement_text": "# Report",
                    "rationale": "r",
                }
            ]
        )
    )

    assert result.startswith("Recorded issue-1")
    assert reporter.issues[0].edits == []


def test_proposing_edits_requires_the_document_text():
    with pytest.raises(ValueError):
        IssueReporter(propose_edits=True)


def test_edits_do_not_change_the_duplicate_fingerprint():
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    report_issue = _tools(reporter)["report_issue"]

    assert report_issue.invoke(_issue_with_edits([])).startswith("Recorded issue-1")
    duplicate = report_issue.invoke(
        _issue_with_edits(
            [
                {
                    "original_text": "# Title",
                    "replacement_text": "# Report",
                    "rationale": "r",
                }
            ]
        )
    )

    assert "duplicate ignored" in duplicate
    assert len(reporter.issues) == 1
    assert reporter.issues[0].edits == []


def test_tool_schema_exposes_typed_edits():
    schema = _tools(IssueReporter(propose_edits=True, document_text=_DOCUMENT))[
        "report_issue"
    ].args_schema.model_json_schema()
    edit_properties = schema["$defs"]["ProposedEditInput"]["properties"]

    assert set(edit_properties) == {
        "original_text",
        "replacement_text",
        "rationale",
    }
    assert schema["$defs"]["ProposedEditInput"]["required"] == [
        "original_text",
        "replacement_text",
        "rationale",
    ]


def test_tool_description_tells_the_agent_when_not_to_propose_an_edit():
    # The docstring is wrapped, so compare against a single-spaced copy.
    reporter = IssueReporter(propose_edits=True, document_text=_DOCUMENT)
    description = " ".join(_tools(reporter)["report_issue"].description.split())
    assert "Propose an edit only when the fix is fully determined" in description
    assert "must not cross a line break" in description
    assert "Set `suggested_action` as well" in description
