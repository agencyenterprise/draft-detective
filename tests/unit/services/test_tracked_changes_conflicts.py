"""Tests for two proposed edits competing for the same words.

Within one markdown line, and across two lines that map into one Word
paragraph: one edit wins by the shared policy and the rest are reported.
"""

from pathlib import Path
from typing import Dict, Sequence, Tuple

import pytest
from docx import Document as PythonDocxDocument

from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.services.docx.tracked_changes import apply_tracked_changes
from lib.workflows.models import SeverityEnum

from tests.unit.services.tracked_changes_support import (
    docx_path,  # noqa: F401 -- a fixture, reached by name
    make_edit as _edit,
    plan_edits as _plan,
    read_document as _read,
    statuses as _statuses,
)

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
