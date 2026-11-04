"""Tests for redlining a quote that carries footnote references.

The markdown writes a footnote reference as a link (`[[1]](#footnote-2)`), and
Word carries it as a mark with no characters in the paragraph's text. The
documents here carry a real ``w:footnoteReference`` run, so the redlines are
checked against the mark Word would show: present once, in its place, and never
inside a deletion or an insertion.
"""

import re
import uuid
import zipfile
from pathlib import Path

import pytest
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from lib.models.issue_edit import IssueEdit
from lib.services.docx.tracked_changes import apply_tracked_changes
from lib.services.docx.tracked_changes.footnotes import (
    FOOTNOTES_CHANGED,
    INSERTS_AT_FOOTNOTE,
    place_around_footnotes,
)
from lib.services.docx.tracked_changes.models import PlannedEdit
from lib.services.docx.tracked_changes.planning import _resolve_paragraph_overlaps
from lib.workflows.models import SeverityEnum
from tests.unit.services.docx.lean_docx import new_document
from tests.unit.services.docx.tracked_changes.support import (
    make_candidates as _candidates,
)
from tests.unit.services.docx.tracked_changes.support import (
    make_edit as _edit,
)
from tests.unit.services.docx.tracked_changes.support import (
    plan_edits as _plan,
)
from tests.unit.services.docx.tracked_changes.support import (
    statuses as _statuses,
)

_MARK = "[[1]](#footnote-2)"


def _footnoted_docx(path: Path, before: str, after: str) -> Path:
    """One paragraph, `before` + a footnote reference mark + `after`."""
    document = new_document()
    paragraph = document.add_paragraph(before)
    reference = OxmlElement("w:r")
    mark = OxmlElement("w:footnoteReference")
    mark.set(qn("w:id"), "1")
    reference.append(mark)
    paragraph._p.append(reference)
    paragraph.add_run(after)
    document.save(str(path))
    return path


def _accepted(path: Path) -> str:
    """The paragraph as it reads with every change accepted, the mark as ``^1``."""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode()
    for change in re.findall(r"<w:(?:del|ins)\b.*?</w:(?:del|ins)>", xml, re.S):
        assert "footnoteReference" not in change
    assert xml.count("<w:footnoteReference") == 1
    body = re.sub(r"<w:del\b.*?</w:del>", "", xml, flags=re.S)
    body = re.sub(r"<w:footnoteReference[^>]*/>", "<w:t>^1</w:t>", body)
    return "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", body))


async def _plan_and_apply(path: Path, line: str, edit: IssueEdit):
    plan, _ = await _plan(
        path, [edit], paragraph_line_ranges={0: (1, 1)}, markdown=line
    )
    written = await apply_tracked_changes(
        str(path), plan.planned, workspace_root=str(path.parent)
    )
    return plan, written


class TestAQuoteEndingOnAFootnote:
    @pytest.mark.asyncio
    async def test_the_sentence_is_rewritten_and_the_mark_stays_at_its_end(
        self, tmp_path: Path
    ):
        before = "Some standards become law. ASTM D4814 was incorporated by the EPA."
        line = f"{before}{_MARK}"
        path = _footnoted_docx(tmp_path / "end.docx", before, "")
        edit = _edit(
            f"ASTM D4814 was incorporated by the EPA.{_MARK}",
            f"The EPA incorporated ASTM D4814.{_MARK}",
            1,
        )

        plan, written = await _plan_and_apply(path, line, edit)

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert _statuses(written) == {edit.id: "applied"}
        assert [p.find for p in plan.planned] == [
            "ASTM D4814 was incorporated by the EPA."
        ]
        assert (
            _accepted(path)
            == "Some standards become law. The EPA incorporated ASTM D4814.^1"
        )


class TestAQuoteCrossingAFootnote:
    @pytest.mark.asyncio
    async def test_a_change_on_one_side_redlines_only_that_side(self, tmp_path: Path):
        before, after = "Companies guard research closely,", " and rules vary by place."
        path = _footnoted_docx(tmp_path / "one-side.docx", before, after)
        edit = _edit(
            f"closely,{_MARK} and rules vary",
            f"closely,{_MARK} and rules differ",
            1,
        )

        plan, _ = await _plan_and_apply(path, f"{before}{_MARK}{after}", edit)

        assert [(p.find, p.replace_with) for p in plan.planned] == [
            ("and rules vary", "and rules differ")
        ]
        assert (
            _accepted(path)
            == "Companies guard research closely,^1 and rules differ by place."
        )

    @pytest.mark.asyncio
    async def test_changes_on_both_sides_are_two_redlines_around_the_mark(
        self, tmp_path: Path
    ):
        before, after = (
            "Off-grid approaches, called bridge power,",
            " were not considered.",
        )
        path = _footnoted_docx(tmp_path / "both.docx", before, after)
        edit = _edit(
            f"{before}{_MARK}{after}",
            f"We did not consider off-grid approaches, called bridge power,{_MARK}.",
            1,
        )

        plan, written = await _plan_and_apply(path, f"{before}{_MARK}{after}", edit)

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert len(plan.planned) == 2
        assert {outcome.status for outcome in written} == {"applied"}
        assert _accepted(path) == (
            "We did not consider off-grid approaches, called bridge power,^1."
        )

    @pytest.mark.asyncio
    async def test_moving_the_mark_rewrites_the_words_around_it(self, tmp_path: Path):
        before, after = "Companies guard research closely,", " and rules vary."
        path = _footnoted_docx(tmp_path / "moved.docx", before, after)
        edit = _edit(
            f"closely,{_MARK} and rules vary.",
            f"closely, and rules vary.{_MARK}",
            1,
        )

        plan, _ = await _plan_and_apply(path, f"{before}{_MARK}{after}", edit)

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert _accepted(path) == "Companies guard research closely, and rules vary.^1"

    @pytest.mark.asyncio
    async def test_moving_the_mark_across_a_space_is_written(self, tmp_path: Path):
        before, after = "Prices rose ", "sharply."
        path = _footnoted_docx(tmp_path / "space.docx", before, after)
        edit = _edit(f"rose {_MARK}sharply", f"rose{_MARK} sharply", 1)

        plan, _ = await _plan_and_apply(path, f"{before}{_MARK}{after}", edit)

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert _accepted(path) == "Prices rose^1 sharply."

    @pytest.mark.asyncio
    async def test_dropping_the_mark_is_reported_not_written(self, tmp_path: Path):
        before, after = "Companies guard research closely,", " and rules vary."
        path = _footnoted_docx(tmp_path / "dropped.docx", before, after)
        edit = _edit(f"closely,{_MARK} and rules", "closely, and rules", 1)

        plan, _ = await _plan_and_apply(path, f"{before}{_MARK}{after}", edit)

        assert plan.planned == []
        assert plan.outcomes[0].status == "unsupported"
        assert plan.outcomes[0].detail == FOOTNOTES_CHANGED


def _edit_row(
    display_text: str, display_replacement: str, original: str, replacement: str
) -> IssueEdit:
    return IssueEdit(
        id=uuid.uuid4(),
        issue_id=uuid.uuid4(),
        position=0,
        original_text=original,
        replacement_text=replacement,
        display_text=display_text,
        display_occurrence=0,
        display_replacement=display_replacement,
        start_line=1,
        end_line=1,
        rationale="r",
    )


class TestPlacingAroundFootnotes:
    def test_an_insertion_with_no_quoted_words_beside_the_mark_is_reported(self):
        edit = _edit_row(
            "rose.[1]", "rose.[1] Sharply.", f"rose.{_MARK}", f"rose.{_MARK} Sharply."
        )

        placed = place_around_footnotes(edit, "Output rose. Then it fell.")

        assert placed.pieces == []
        assert placed.detail == INSERTS_AT_FOOTNOTE

    def test_a_quote_the_paragraph_repeats_is_not_placed(self):
        edit = _edit_row("rose.[1]", "fell.[1]", f"rose.{_MARK}", f"fell.{_MARK}")

        placed = place_around_footnotes(edit, "Output rose. Prices rose.")

        assert placed.pieces == []
        assert placed.detail is None

    def test_a_stretch_repeated_outside_the_quote_is_found_inside_it(self):
        paragraph = "It rose. Output rose and then fell."
        edit = _edit_row(
            "Output rose[1] and then fell.",
            "Output climbed[1] and then fell.",
            f"Output rose{_MARK} and then fell.",
            f"Output climbed{_MARK} and then fell.",
        )

        placed = place_around_footnotes(edit, paragraph)

        assert [paragraph[slice(*p.span)] for p in placed.pieces] == ["Output rose"]
        assert [p.replace_with for p in placed.pieces] == ["Output climbed"]

    def test_neighbouring_redlines_never_share_the_space_between_them(self):
        paragraph = "Alpha beta gamma."
        edit = _edit_row(
            "Alpha [1] beta gamma.",
            "One[1]two gamma.",
            f"Alpha {_MARK} beta gamma.",
            f"One{_MARK}two gamma.",
        )

        placed = place_around_footnotes(edit, paragraph)

        spans = [p.span for p in placed.pieces]
        assert len(spans) == 2
        assert spans[0][1] <= spans[1][0]


class TestOverlapsOfAnEditPlacedInPieces:
    def test_losing_one_piece_drops_the_whole_edit(self):
        pieced = _edit("a", "b", 1)
        rival = _edit("c", "d", 1)
        candidates = _candidates([pieced, rival], [SeverityEnum.LOW, SeverityEnum.HIGH])
        by_id = {candidate.edit.id: candidate for candidate in candidates}

        def planned(edit_id: uuid.UUID, span: tuple[int, int]) -> PlannedEdit:
            return PlannedEdit(
                edit_id=edit_id,
                paragraph_ref="P1#x",
                paragraph_index=0,
                find="x",
                replace_with="y",
                occurrence=0,
                span=span,
            )

        kept, losses = _resolve_paragraph_overlaps(
            [
                planned(pieced.id, (0, 5)),
                planned(pieced.id, (10, 15)),
                planned(rival.id, (12, 20)),
            ],
            by_id,
        )

        assert [edit.edit_id for edit in kept] == [rival.id]
        assert [(loss.edit_id, loss.winner_id) for loss in losses] == [
            (pieced.id, rival.id)
        ]

    @staticmethod
    def _planned(edit_id: uuid.UUID, span: tuple[int, int]) -> PlannedEdit:
        return PlannedEdit(
            edit_id=edit_id,
            paragraph_ref="P1#x",
            paragraph_index=0,
            find="x",
            replace_with="y",
            occurrence=0,
            span=span,
        )

    def test_an_edit_beaten_only_by_a_dropped_edit_loses_to_the_kept_one(self):
        pieced, strong, weak = (
            _edit("a", "b", 1),
            _edit("c", "d", 1),
            _edit("e", "f", 1),
        )
        candidates = _candidates(
            [pieced, strong, weak],
            [SeverityEnum.MEDIUM, SeverityEnum.HIGH, SeverityEnum.LOW],
        )
        by_id = {candidate.edit.id: candidate for candidate in candidates}

        # `pieced` loses its first redline's overlap to `strong` and would win
        # its second against `weak`; deciding the two apart would leave
        # `weak` beaten by an edit that is not in the document.
        kept, losses = _resolve_paragraph_overlaps(
            [
                self._planned(pieced.id, (0, 5)),
                self._planned(pieced.id, (10, 15)),
                self._planned(strong.id, (2, 4)),
                self._planned(weak.id, (12, 20)),
            ],
            by_id,
        )

        assert [edit.edit_id for edit in kept] == [strong.id]
        assert {loss.edit_id: loss.winner_id for loss in losses} == {
            pieced.id: strong.id,
            weak.id: strong.id,
        }

    def test_a_loser_to_a_pieced_edit_that_itself_lost_names_a_kept_winner(self):
        """Review probe (BOTO-83): B loses to A on A's first piece, A loses to C
        on its second. Every loss must name an edit that is in the document."""
        pieced, low, high = _edit("a", "b", 1), _edit("e", "f", 1), _edit("c", "d", 1)
        candidates = _candidates(
            [pieced, low, high],
            [SeverityEnum.MEDIUM, SeverityEnum.LOW, SeverityEnum.HIGH],
        )
        by_id = {candidate.edit.id: candidate for candidate in candidates}

        kept, losses = _resolve_paragraph_overlaps(
            [
                self._planned(pieced.id, (0, 5)),
                self._planned(pieced.id, (10, 15)),
                self._planned(low.id, (2, 4)),
                self._planned(high.id, (12, 20)),
            ],
            by_id,
        )

        kept_ids = {edit.edit_id for edit in kept}
        assert kept_ids == {high.id}
        for loss in losses:
            assert loss.winner_id in kept_ids, (loss.edit_id, loss.winner_id)
