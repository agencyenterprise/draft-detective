"""Tests for writing proposed edits into a DOCX as Word tracked changes.

Everything here runs against a real .docx built in ``tmp_path`` and read back
with docx-editor, so the redlines are checked as Word would see them.
"""

import uuid
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pytest
from docx import Document as PythonDocxDocument
from docx_editor import Document as EditorDocument

from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.services.docx.edit_notes import build_edit_notes
from lib.services.docx.paragraph_refs import map_paragraph_refs
from lib.services.docx.tracked_changes import (
    EditOutcome,
    apply_tracked_changes,
    plan_tracked_changes,
)
from lib.services.edit_conflicts import EditCandidate, resolve_edit_conflicts
from lib.workflows.models import SeverityEnum
from lib.workflows.simple_deep_agent.edit_anchoring import document_lines
from datetime import UTC, datetime

# The document under test. A non-breaking space inside prose and a phrase
# repeated in one paragraph are both ordinary in converted DOCX documents; the
# table comes first on purpose, so a naive index alignment between python-docx
# and docx-editor would redline a table cell.
_BODY = [
    "The Energy\u00a0Supply chapter reports a 14% rise in output for 2019.",
    "Figure 3 and Figure 3 close the section.",
    "Shared caption text",
]
_CELLS = ["Shared caption text", "Other cell"]

# The markdown the edits were anchored against. Line 1 carries a trailing
# clause the DOCX paragraph does not, standing in for conversion drift.
_MARKDOWN = "\n".join(
    [
        "The Energy\u00a0Supply chapter reports a 14% rise in output for 2019, per Table 2.",
        "Figure 3 and **Figure 3** close the section.",
        "Shared caption text",
    ]
)
_PARAGRAPH_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 1), 1: (2, 2), 2: (3, 3)}


@pytest.fixture
def docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = _CELLS[0]
    table.cell(0, 1).text = _CELLS[1]
    for text in _BODY:
        document.add_paragraph(text)
    path = tmp_path / "main.docx"
    document.save(str(path))
    return path


def _edit(
    original_text: str,
    replacement_text: str,
    start_line: int,
    *,
    status: IssueEditStatus = IssueEditStatus.PROPOSED,
    edit_id: uuid.UUID | None = None,
) -> IssueEdit:
    return IssueEdit(
        id=edit_id or uuid.uuid4(),
        issue_id=uuid.uuid4(),
        position=0,
        original_text=original_text,
        replacement_text=replacement_text,
        start_line=start_line,
        end_line=start_line,
        rationale="because the figure is misnumbered",
        status=status,
    )


def _candidates(
    edits: Sequence[IssueEdit], severities: Sequence[SeverityEnum] | None = None
) -> List[EditCandidate]:
    chosen = severities or [SeverityEnum.MEDIUM] * len(edits)
    return [
        EditCandidate(
            edit=edit,
            issue_severity=severity,
            issue_created_at=datetime(2026, 1, 1, tzinfo=UTC),
            workflow_type="reference_validation_v2",
        )
        for edit, severity in zip(edits, chosen)
    ]


async def _plan(
    path: Path,
    edits: Sequence[IssueEdit],
    severities: Sequence[SeverityEnum] | None = None,
    paragraph_line_ranges: Dict[int, Tuple[int, int]] | None = None,
    markdown: str | None = None,
):
    candidates = _candidates(edits, severities)
    lines = document_lines(_MARKDOWN if markdown is None else markdown)
    decisions = resolve_edit_conflicts(candidates, lines)
    plan = await plan_tracked_changes(
        str(path),
        decisions,
        {candidate.edit.id: candidate for candidate in candidates},
        (
            _PARAGRAPH_LINE_RANGES
            if paragraph_line_ranges is None
            else paragraph_line_ranges
        ),
        lines,
        workspace_root=str(path.parent),
    )
    return plan, decisions


def _statuses(outcomes: Sequence[EditOutcome]) -> Dict[uuid.UUID, str]:
    return {outcome.edit_id: outcome.status for outcome in outcomes}


def _read(path: Path):
    doc = EditorDocument.open(
        path, author="Reader", workspace_dir=str(path.parent / "read-ws")
    )
    try:
        return doc.get_visible_text(), doc.get_original_text(), doc.list_revisions()
    finally:
        doc.close()


class TestPlanAndApply:
    @pytest.mark.asyncio
    async def test_a_located_edit_becomes_a_tracked_replacement(self, docx_path: Path):
        edit = _edit("14% rise", "18% rise", 1)

        plan, _ = await _plan(docx_path, [edit])
        outcomes = await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert _statuses(outcomes) == {edit.id: "applied"}
        visible, original, revisions = _read(docx_path)
        assert "reports a 18% rise in output" in visible
        assert "reports a 14% rise in output" in original
        # One deletion and one insertion, narrowed by the library to the part
        # of the quote that actually changes.
        assert [r.type for r in revisions] == ["deletion", "insertion"]
        assert revisions[0].text in "14% rise"
        assert revisions[1].text in "18% rise"

    @pytest.mark.asyncio
    async def test_a_quote_drifting_on_a_non_breaking_space_still_matches(
        self, docx_path: Path
    ):
        edit = _edit("Energy Supply chapter", "Energy Demand chapter", 1)

        plan, _ = await _plan(docx_path, [edit])
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        # The search string handed to Word keeps the document's own spacing.
        assert plan.planned[0].find == "Energy\u00a0Supply chapter"
        visible, _, _ = _read(docx_path)
        assert "The Energy Demand chapter reports" in visible

    @pytest.mark.asyncio
    async def test_an_empty_replacement_is_a_tracked_deletion(self, docx_path: Path):
        edit = _edit("for 2019", "", 1)

        plan, _ = await _plan(docx_path, [edit])
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        visible, original, revisions = _read(docx_path)
        assert "for 2019" not in visible
        assert "for 2019" in original
        assert [(r.type, r.text) for r in revisions] == [("deletion", "for 2019")]

    @pytest.mark.asyncio
    async def test_several_edits_in_one_paragraph_are_all_written(
        self, docx_path: Path
    ):
        first = _edit("Energy Supply", "Energy Demand", 1)
        second = _edit("14% rise", "18% rise", 1)

        plan, _ = await _plan(docx_path, [first, second])
        outcomes = await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        assert _statuses(outcomes) == {first.id: "applied", second.id: "applied"}
        visible, _, _ = _read(docx_path)
        assert "The Energy Demand chapter reports a 18% rise in output" in visible

    @pytest.mark.asyncio
    async def test_edits_in_different_paragraphs_are_all_written(self, docx_path: Path):
        first = _edit("14% rise", "18% rise", 1)
        second = _edit("Shared caption text", "Shared caption wording", 3)

        plan, _ = await _plan(docx_path, [first, second])
        outcomes = await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        assert _statuses(outcomes) == {first.id: "applied", second.id: "applied"}
        visible, _, _ = _read(docx_path)
        assert "18% rise" in visible
        assert "Shared caption wording" in visible


class TestParagraphResolution:
    @pytest.mark.asyncio
    async def test_a_repeated_phrase_uses_the_occurrence_the_source_settles(
        self, docx_path: Path
    ):
        # Unique in the markdown as `**Figure 3**`, the second of two identical
        # spans once the emphasis is stripped.
        edit = _edit("**Figure 3**", "Figure 4", 2)

        plan, _ = await _plan(docx_path, [edit])
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        assert plan.planned[0].occurrence == 1
        visible, _, _ = _read(docx_path)
        assert "Figure 3 and Figure 4 close the section." in visible

    @pytest.mark.asyncio
    async def test_a_table_cell_never_takes_a_body_paragraph_redline(
        self, docx_path: Path
    ):
        edit = _edit("Shared caption text", "Shared caption wording", 3)

        plan, _ = await _plan(docx_path, [edit])
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        reopened = PythonDocxDocument(str(docx_path))
        assert reopened.tables[0].cell(0, 0).text == "Shared caption text"
        assert reopened.tables[0].cell(0, 1).text == "Other cell"
        visible, _, _ = _read(docx_path)
        assert "Shared caption wording" in visible

    @pytest.mark.asyncio
    async def test_a_quote_the_paragraph_does_not_carry_is_not_found(
        self, docx_path: Path
    ):
        # On the markdown line, absent from the converted paragraph.
        edit = _edit("per Table 2", "per Table 3", 1)

        plan, _ = await _plan(docx_path, [edit])

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "not_found"}

    @pytest.mark.asyncio
    async def test_an_edit_whose_line_maps_to_no_paragraph_is_not_found(
        self, docx_path: Path
    ):
        edit = _edit("14% rise", "18% rise", 1)

        plan, _ = await _plan(docx_path, [edit], paragraph_line_ranges={})

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "not_found"}

    @pytest.mark.asyncio
    async def test_a_quote_the_line_carries_twice_never_reaches_the_plan(
        self, docx_path: Path
    ):
        edit = _edit("Figure 3", "Figure 4", 2)

        plan, _ = await _plan(docx_path, [edit])

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unlocatable"}


# A paragraph followed by a table, with the paragraph's own figure repeated in
# a cell. The line-range mapper runs a body paragraph's range up to the line
# before the next body paragraph starts, so the table's markdown rows fall
# inside paragraph 1's range -- the ranges below are that map, by hand.
_TABLE_MARKDOWN = "\n".join(
    [
        "# Title",
        "",
        "Output increased by 14%.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        "| Growth | 14% |",
    ]
)
_TABLE_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 1), 1: (3, 7)}

_TABLE_DETAIL = (
    "the edit's line is not part of the mapped paragraph (a table or nested block)"
)


@pytest.fixture
def table_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph("Title")
    document.add_paragraph("Output increased by 14%.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Growth"
    table.cell(1, 1).text = "14%"
    path = tmp_path / "table.docx"
    document.save(str(path))
    return path


class TestATableLineNeverRedlinesTheParagraphAbove:
    @pytest.mark.asyncio
    async def test_a_table_cell_edit_is_reported_rather_than_misplaced(
        self, table_docx_path: Path
    ):
        edit = _edit("14%", "18%", 7)

        plan, _ = await _plan(
            table_docx_path,
            [edit],
            paragraph_line_ranges=_TABLE_LINE_RANGES,
            markdown=_TABLE_MARKDOWN,
        )
        await apply_tracked_changes(
            str(table_docx_path),
            plan.planned,
            workspace_root=str(table_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unlocatable"}
        assert [outcome.detail for outcome in plan.outcomes] == [_TABLE_DETAIL]
        visible, _, revisions = _read(table_docx_path)
        assert "Output increased by 14%." in visible
        assert list(revisions) == []

    @pytest.mark.asyncio
    async def test_the_same_quote_on_the_paragraphs_own_line_is_applied(
        self, table_docx_path: Path
    ):
        edit = _edit("14%", "18%", 3)

        plan, _ = await _plan(
            table_docx_path,
            [edit],
            paragraph_line_ranges=_TABLE_LINE_RANGES,
            markdown=_TABLE_MARKDOWN,
        )
        await apply_tracked_changes(
            str(table_docx_path),
            plan.planned,
            workspace_root=str(table_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, revisions = _read(table_docx_path)
        assert "Output increased by 18%." in visible
        assert [r.type for r in revisions] == ["deletion", "insertion"]


_FOOTNOTE_PARAGRAPH = "The protocol was applied to the second cohort in 2019."
_FOOTNOTE_MARKDOWN = (
    "The protocol was applied to the second cohort [[1]](#footnote-2) in 2019."
)


@pytest.fixture
def footnote_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_FOOTNOTE_PARAGRAPH)
    path = tmp_path / "footnote.docx"
    document.save(str(path))
    return path


class TestAFootnoteReferenceIsNotDrift:
    @pytest.mark.asyncio
    async def test_a_marker_in_the_middle_of_the_line_still_allows_the_edit(
        self, footnote_docx_path: Path
    ):
        # Word carries the footnote as a reference mark, so the marker is on
        # the markdown line and nowhere in the paragraph's text.
        edit = _edit("second cohort", "third cohort", 1)

        plan, _ = await _plan(
            footnote_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_FOOTNOTE_MARKDOWN,
        )
        await apply_tracked_changes(
            str(footnote_docx_path),
            plan.planned,
            workspace_root=str(footnote_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(footnote_docx_path)
        assert "applied to the third cohort in 2019." in visible


_SHORT_PARAGRAPH = "Yield rose 14%."


@pytest.fixture
def short_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_SHORT_PARAGRAPH)
    path = tmp_path / "short.docx"
    document.save(str(path))
    return path


class TestAShortParagraphHasNoPrefixToFallBackOn:
    @pytest.mark.asyncio
    async def test_a_line_that_merely_shares_the_quote_is_rejected(
        self, short_docx_path: Path
    ):
        edit = _edit("14%", "18%", 1)

        plan, _ = await _plan(
            short_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown="Costs fell 14%.",
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unlocatable"}
        assert [outcome.detail for outcome in plan.outcomes] == [_TABLE_DETAIL]

    @pytest.mark.asyncio
    async def test_its_own_line_is_accepted(self, short_docx_path: Path):
        edit = _edit("14%", "18%", 1)

        plan, _ = await _plan(
            short_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_SHORT_PARAGRAPH,
        )
        await apply_tracked_changes(
            str(short_docx_path),
            plan.planned,
            workspace_root=str(short_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(short_docx_path)
        assert "Yield rose 18%." in visible

    @pytest.mark.asyncio
    async def test_a_leading_footnote_marker_is_not_counted_against_it(
        self, short_docx_path: Path
    ):
        # Too short for the shared-prefix rule to help, and the marker sits
        # where a prefix would start: only dropping it settles the line.
        edit = _edit("14%", "18%", 1)

        plan, _ = await _plan(
            short_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=f"[[1]](#footnote-2) {_SHORT_PARAGRAPH}",
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}


_JOINED_MARKDOWN = "This is aword."
_JOINED_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 1)}


@pytest.fixture
def joined_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_JOINED_MARKDOWN)
    path = tmp_path / "joined.docx"
    document.save(str(path))
    return path


class TestTheReplacementReachesWordAsWritten:
    async def _plan_joined(self, path: Path, edit: IssueEdit):
        return await _plan(
            path,
            [edit],
            paragraph_line_ranges=_JOINED_LINE_RANGES,
            markdown=_JOINED_MARKDOWN,
        )

    @pytest.mark.asyncio
    async def test_a_replacement_that_only_adds_a_space_keeps_it(
        self, joined_docx_path: Path
    ):
        edit = _edit("word", " word", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)
        await apply_tracked_changes(
            str(joined_docx_path),
            plan.planned,
            workspace_root=str(joined_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert plan.planned[0].replace_with == " word"
        visible, original, _ = _read(joined_docx_path)
        assert "This is a word." in visible
        assert "This is aword." in original

    @pytest.mark.asyncio
    async def test_a_replacement_carrying_a_newline_is_unsupported(
        self, joined_docx_path: Path
    ):
        edit = _edit("aword", "a\nword", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)
        await apply_tracked_changes(
            str(joined_docx_path),
            plan.planned,
            workspace_root=str(joined_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "the replacement spans more than one paragraph"
        ]
        visible, _, revisions = _read(joined_docx_path)
        assert visible.strip() == "This is aword."
        assert list(revisions) == []

    @pytest.mark.asyncio
    async def test_a_replacement_that_only_reformats_the_text_is_unsupported(
        self, joined_docx_path: Path
    ):
        edit = _edit("aword", "**aword**", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "the replacement matches the current text once formatting is removed"
        ]


_REFERENCE_MARKDOWN = "Smith et al. 2019. Annual report."


@pytest.fixture
def reference_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_REFERENCE_MARKDOWN)
    path = tmp_path / "reference.docx"
    document.save(str(path))
    return path


class TestAMidLineNumberIsNotAListMarker:
    @pytest.mark.asyncio
    async def test_a_quote_opening_with_a_year_keeps_it(
        self, reference_docx_path: Path
    ):
        edit = _edit("2019. Annual report", "2021. Annual report", 1)

        plan, _ = await _plan(
            reference_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_REFERENCE_MARKDOWN,
        )
        await apply_tracked_changes(
            str(reference_docx_path),
            plan.planned,
            workspace_root=str(reference_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert plan.planned[0].find == "2019. Annual report"
        visible, original, _ = _read(reference_docx_path)
        assert "Smith et al. 2021. Annual report." in visible
        assert "Smith et al. 2019. Annual report." in original


# One Word paragraph, two markdown lines: the second list line falls inside
# paragraph 0's line range (the mapper runs a paragraph's range up to the line
# before the next body paragraph), and it opens with the paragraph's own words,
# so both lines resolve into the same passage. Quotes from the two lines can
# then cover the same characters although no line-level conflict exists.
_ONE_PARAGRAPH_TWO_LINES = "The committee recommends increasing the 2019 budget by 14%."
_TWO_LINE_MARKDOWN = "\n".join(
    [
        _ONE_PARAGRAPH_TWO_LINES,
        "The committee recommends increasing the 2020 budget by 9%.",
    ]
)
_TWO_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 2)}


@pytest.fixture
def two_line_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_ONE_PARAGRAPH_TWO_LINES)
    path = tmp_path / "two-line.docx"
    document.save(str(path))
    return path


class TestTwoLinesLandingInOneParagraph:
    async def _plan_two_line(
        self,
        path: Path,
        edits: Sequence[IssueEdit],
        severities: Sequence[SeverityEnum] | None = None,
    ):
        return await _plan(
            path,
            edits,
            severities,
            paragraph_line_ranges=_TWO_LINE_RANGES,
            markdown=_TWO_LINE_MARKDOWN,
        )

    @pytest.mark.asyncio
    async def test_an_accepted_edit_on_the_later_line_beats_the_earlier_one(
        self, two_line_docx_path: Path
    ):
        # Planned second, and the winner regardless: the policy is the same one
        # that settles two quotes of a single line.
        earlier = _edit("increasing the 2019 budget", "increasing the 2021 budget", 1)
        accepted = _edit(
            "committee recommends increasing",
            "committee urges increasing",
            2,
            status=IssueEditStatus.ACCEPTED,
        )

        plan, _ = await self._plan_two_line(two_line_docx_path, [earlier, accepted])
        outcomes = await apply_tracked_changes(
            str(two_line_docx_path),
            plan.planned,
            workspace_root=str(two_line_docx_path.parent),
        )

        assert [edit.edit_id for edit in plan.planned] == [accepted.id]
        assert _statuses(plan.outcomes) == {
            earlier.id: "conflict",
            accepted.id: "applied",
        }
        assert _statuses(outcomes) == {accepted.id: "applied"}
        loss = next(o for o in plan.outcomes if o.edit_id == earlier.id)
        assert loss.winner_id == accepted.id
        assert loss.detail == f"overlaps proposed edit {accepted.id} in this paragraph"
        visible, _, _ = _read(two_line_docx_path)
        assert "The committee urges increasing the 2019 budget" in visible

    @pytest.mark.asyncio
    async def test_the_higher_severity_wins_when_both_are_proposed(
        self, two_line_docx_path: Path
    ):
        earlier = _edit("increasing the 2019 budget", "increasing the 2021 budget", 1)
        later = _edit(
            "committee recommends increasing", "committee urges increasing", 2
        )

        plan, _ = await self._plan_two_line(
            two_line_docx_path,
            [earlier, later],
            [SeverityEnum.LOW, SeverityEnum.HIGH],
        )

        assert [edit.edit_id for edit in plan.planned] == [later.id]
        assert _statuses(plan.outcomes) == {earlier.id: "conflict", later.id: "applied"}

    @pytest.mark.asyncio
    async def test_edits_that_do_not_touch_are_both_written(
        self, two_line_docx_path: Path
    ):
        first = _edit("committee", "board", 1)
        second = _edit("budget by 9%", "budget by 11%", 2)

        plan, _ = await self._plan_two_line(two_line_docx_path, [first, second])

        # The second quote is not in the paragraph at all, so it is reported
        # rather than conflated with the first -- which stands untouched.
        assert [edit.edit_id for edit in plan.planned] == [first.id]
        assert _statuses(plan.outcomes) == {first.id: "applied", second.id: "not_found"}


class TestConflictsNeverReachTheLibrary:
    @pytest.mark.asyncio
    async def test_only_the_winning_edit_of_an_overlap_is_written(
        self, docx_path: Path
    ):
        winner = _edit("a 14% rise in output", "a 14% fall in output", 1)
        loser = _edit("14% rise", "18% rise", 1)

        plan, decisions = await _plan(
            docx_path, [winner, loser], [SeverityEnum.HIGH, SeverityEnum.LOW]
        )
        outcomes = await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        assert [edit.edit_id for edit in plan.planned] == [winner.id]
        assert _statuses(plan.outcomes)[loser.id] == "conflict"
        assert _statuses(outcomes) == {winner.id: "applied"}
        visible, _, revisions = _read(docx_path)
        assert "a 14% fall in output" in visible
        assert "18% rise" not in visible
        assert len(revisions) == 2

    @pytest.mark.asyncio
    async def test_a_rejected_edit_is_left_out_of_the_plan(self, docx_path: Path):
        rejected = _edit("14% rise", "18% rise", 1, status=IssueEditStatus.REJECTED)

        plan, _ = await _plan(docx_path, [rejected])

        assert plan.planned == []
        assert plan.outcomes == []


class TestTheFileStaysReadable:
    @pytest.mark.asyncio
    async def test_python_docx_reopens_the_output_with_untouched_text_intact(
        self, docx_path: Path
    ):
        edits = [
            _edit("14% rise", "18% rise", 1),
            _edit("**Figure 3**", "Figure 4", 2),
        ]

        plan, _ = await _plan(docx_path, edits)
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        paragraphs = [
            p.text
            for p in PythonDocxDocument(str(docx_path)).paragraphs
            if p.text.strip()
        ]
        # The redlined paragraphs no longer read as plain text to python-docx --
        # which is exactly why the comment pass has to run first -- but the
        # untouched one is unchanged.
        assert _BODY[2] in paragraphs

    @pytest.mark.asyncio
    async def test_an_empty_plan_leaves_the_file_alone(self, docx_path: Path):
        before = docx_path.read_bytes()

        assert await apply_tracked_changes(str(docx_path), []) == []
        assert docx_path.read_bytes() == before


class TestParagraphRefMapping:
    def test_a_body_paragraph_is_preferred_over_a_table_cell(self):
        class _Info:
            def __init__(self, ref: str, text: str):
                self.ref = ref
                self.text = text

        editor_paragraphs = [
            _Info("P1#aaaa", "Shared caption text"),
            _Info("P2#bbbb", "Other cell"),
            _Info("P3#cccc", "Shared caption text"),
        ]

        mapped = map_paragraph_refs(
            ["Shared caption text"],
            editor_paragraphs,  # type: ignore[arg-type]
            in_table_refs={"P1#aaaa", "P2#bbbb"},
        )

        assert mapped[0].ref == "P3#cccc"

    def test_an_unmatched_text_stays_unmapped(self):
        assert map_paragraph_refs(["nowhere"], []) == {}


class TestEditNotes:
    def test_an_applied_edit_reads_as_a_tracked_change(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="applied")}, {}
        )

        assert note == (
            'Proposed edit: "14% rise" → "18% rise"\n'
            "because the figure is misnumbered\n"
            "Applied below as a tracked change."
        )

    def test_a_deletion_is_labelled_as_one(self):
        edit = _edit("for 2019", "", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="applied")}, {}
        )

        assert note.startswith('Proposed deletion: "for 2019"\n')

    def test_a_conflict_names_the_workflow_it_lost_to(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit],
            {edit.id: EditOutcome(edit_id=edit.id, status="conflict")},
            {edit.id: "Reference Error Checker"},
        )

        assert note.endswith(
            "Not applied as a tracked change: overlaps another proposed edit "
            "on this line (Reference Error Checker)."
        )

    def test_a_conflict_without_a_named_winner_says_so_plainly(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="conflict")}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: overlaps another proposed edit "
            "in the same paragraph."
        )

    def test_an_unsupported_replacement_says_what_word_cannot_show(self):
        edit = _edit("aword", "a\nword", 1)

        (note,) = build_edit_notes(
            [edit],
            {
                edit.id: EditOutcome(
                    edit_id=edit.id,
                    status="unsupported",
                    detail="the replacement spans more than one paragraph",
                )
            },
            {},
        )

        assert note.endswith(
            "Not applied as a tracked change: the replacement cannot be "
            "represented in Word (the replacement spans more than one "
            "paragraph)."
        )

    def test_an_unsupported_replacement_without_a_detail_stops_at_the_reason(self):
        edit = _edit("aword", "a\nword", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="unsupported")}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: the replacement cannot be "
            "represented in Word."
        )

    def test_a_paragraph_wide_conflict_says_which_paragraph_it_is(self):
        edit = _edit("14% rise", "18% rise", 1)
        winner_id = uuid.uuid4()

        (note,) = build_edit_notes(
            [edit],
            {
                edit.id: EditOutcome(
                    edit_id=edit.id,
                    status="conflict",
                    detail=f"overlaps proposed edit {winner_id} in this paragraph",
                    winner_id=winner_id,
                )
            },
            {edit.id: "Advocacy Tone Check"},
        )

        assert note.endswith(
            "Not applied as a tracked change: overlaps another proposed edit "
            "in this paragraph (Advocacy Tone Check)."
        )

    def test_a_failed_write_says_what_went_wrong(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit],
            {
                edit.id: EditOutcome(
                    edit_id=edit.id,
                    status="failed",
                    detail="text not found in paragraph P3#aaaa",
                )
            },
            {},
        )

        assert note.endswith(
            "Not applied as a tracked change: text not found in paragraph " "P3#aaaa."
        )

    def test_a_failed_write_without_a_detail_still_reads_as_a_failure(self):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status="failed")}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: writing the change to Word failed."
        )

    @pytest.mark.parametrize("status", ["unlocatable", "not_found", "ambiguous"])
    def test_every_unmatched_outcome_reads_the_same(self, status):
        edit = _edit("14% rise", "18% rise", 1)

        (note,) = build_edit_notes(
            [edit], {edit.id: EditOutcome(edit_id=edit.id, status=status)}, {}
        )

        assert note.endswith(
            "Not applied as a tracked change: the quoted text could not be "
            "matched in this paragraph."
        )

    def test_an_edit_with_no_outcome_is_left_out(self):
        edit = _edit("14% rise", "18% rise", 1, status=IssueEditStatus.REJECTED)

        assert build_edit_notes([edit], {}, {}) == []
